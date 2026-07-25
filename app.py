import streamlit as st
from supabase import create_client, Client
import requests
from bs4 import BeautifulSoup
import random
import json

# --- SUPABASE CLIENT & KONFIGURATION ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- USER-ID ---
# Da st.context.user in der kostenlosen Umgebung nicht verfügbar ist, nutzen wir einen festen Gast-User
user_id = "gast_user"

st.write(f"Eingeloggt als: {user_id}")

# --- FUNKTIONEN ---
def fetch_chefkoch_recipe(is_veg):
    search_term = "Rezept"
    search_url = f"https://www.chefkoch.de/rs/s0/{search_term}/Rezepte.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if '/rezepte/' in a['href']]
        random.shuffle(links)
        
        for link in links[:5]:
            resp = requests.get(link, headers=headers)
            s = BeautifulSoup(resp.text, 'html.parser')
            script = s.find('script', {'type': 'application/ld+json'})
            if script:
                data = json.loads(script.string)
                recipe = next((item for item in (data if isinstance(data, list) else [data]) 
                              if item.get('@type') == 'Recipe'), None)
                if recipe:
                    name = recipe.get('name', '')
                    if is_veg and any(k in name.lower() for k in ["huhn", "fleisch", "fisch", "speck"]):
                        continue
                    return {"name": name, "zutaten": recipe.get('recipeIngredient', []), "url": link}
    except Exception as e:
        st.error(f"Fehler beim Laden: {e}")
    return None

# --- APP UI ---
st.title("👨‍🍳 Chefkoch Smart-App")
veg_choice = st.radio("Ernährungsweise:", ["Vegetarisch", "Mit Fleisch"], key="veg_radio")

if st.button("Neues Rezept suchen", key="btn_suche"):
    st.session_state.current_recipe = fetch_chefkoch_recipe(veg_choice == "Vegetarisch")

if 'current_recipe' in st.session_state and st.session_state.current_recipe:
    r = st.session_state.current_recipe
    st.subheader(r["name"])
    st.write("Zutaten:", r["zutaten"])
    st.link_button("Zum Originalrezept", r["url"])
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Zutaten speichern", key="save_zutaten"):
            for zutat in r["zutaten"]:
                supabase.table("einkaufsliste").insert({
                    "user_id": user_id,
                    "rezept_name": r["name"],
                    "zutat": zutat
                }).execute()
            st.success("Zutaten gespeichert!")
            
    with col2:
        if st.button("❤️ Ich mag das!", key="save_fav"):
            supabase.table("favoriten").insert({
                "user_id": user_id,
                "rezept_name": r["name"],
                "url": r["url"],
                "zutaten": r["zutaten"]
            }).execute()
            st.success("Gespeichert!")

# --- SIDEBAR ---
st.sidebar.title("🛒 Deine Einkaufsliste")
einkauf_data = supabase.table("einkaufsliste").select("*").eq("user_id", user_id).execute().data

if einkauf_data:
    grouped = {}
    for item in einkauf_data:
        grouped.setdefault(item['rezept_name'], []).append(item['zutat'])
    
    for name, zutaten in grouped.items():
        with st.sidebar.expander(f"📦 {name}"):
            for z in zutaten:
                st.write(f"- {z}")
                
    if st.sidebar.button("Liste löschen", key="clear_list"):
        supabase.table("einkaufsliste").delete().eq("user_id", user_id).execute()
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("⭐ Deine Favoriten")
fav_data = supabase.table("favoriten").select("*").eq("user_id", user_id).execute().data

if fav_data:
    for fav in fav_data:
        st.sidebar.markdown(f"[{fav['rezept_name']}]({fav['url']})")
        if st.sidebar.button(f"🗑️ Löschen {fav['rezept_name'][:10]}", key=f"del_{fav['id']}"):
            supabase.table("favoriten").delete().eq("id", fav['id']).execute()
            st.rerun()
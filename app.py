import streamlit as st
from supabase import create_client
import requests
from bs4 import BeautifulSoup
import random
import datetime

# --- DATENBANK VERBINDUNG ---
# Holt die Daten aus den Secrets der Streamlit Cloud
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- USER-ID ---
# Wir nutzen die E-Mail als User-ID, falls Streamlit-Auth aktiv ist, 
# sonst ein Fallback für lokale Tests
user_info = st.experimental_user
user_id = user_info.email if user_info.is_logged_in else "gast_user"

# --- HELPER FUNKTIONEN ---
def fetch_chefkoch_recipe(is_veg):
    search_term = "Rezept"
    search_url = f"https://www.chefkoch.de/rs/s0/{search_term}/Rezepte.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    links = [a['href'] for a in soup.find_all('a', href=True) if '/rezepte/' in a['href']]
    random.shuffle(links)
    
    for link in links[:5]:
        try:
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
        except: continue
    return None

# --- APP UI ---
st.title("👨‍🍳 Chefkoch Smart-App")
veg_choice = st.radio("Ernährungsweise:", ["Vegetarisch", "Mit Fleisch"])

if st.button("Neues Rezept suchen"):
    st.session_state.current_recipe = fetch_chefkoch_recipe(veg_choice == "Vegetarisch")

if 'current_recipe' in st.session_state and st.session_state.current_recipe:
    r = st.session_state.current_recipe
    st.subheader(r["name"])
    st.write("Zutaten:", r["zutaten"])
    st.link_button("Zum Originalrezept", r["url"])
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Zutaten speichern"):
            # Speichern in Supabase 'einkaufsliste'
            for zutat in r["zutaten"]:
                supabase.table("einkaufsliste").insert({
                    "user_id": user_id,
                    "rezept_name": r["name"],
                    "zutat": zutat
                }).execute()
            st.success("Zutaten gespeichert!")
            
    with col2:
        if st.button("❤️ Ich mag das!"):
            # Speichern in Supabase 'favoriten'
            supabase.table("favoriten").insert({
                "user_id": user_id,
                "rezept_name": r["name"],
                "url": r["url"],
                "zutaten": r["zutaten"]
            }).execute()
            st.success("Gespeichert!")

# --- SIDEBAR ---
st.sidebar.title("🛒 Deine Einkaufsliste")
# Abfrage aus Datenbank
einkauf_data = supabase.table("einkaufsliste").select("*").eq("user_id", user_id).execute().data

if einkauf_data:
    # Gruppierung für die Ansicht
    grouped = {}
    for item in einkauf_data:
        grouped.setdefault(item['rezept_name'], []).append(item['zutat'])
    
    for name, zutaten in grouped.items():
        with st.sidebar.expander(f"📦 {name}"):
            for z in zutaten:
                st.write(f"- {z}")
                
    if st.sidebar.button("Liste löschen"):
        supabase.table("einkaufsliste").delete().eq("user_id", user_id).execute()
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("⭐ Deine Favoriten")
fav_data = supabase.table("favoriten").select("*").eq("user_id", user_id).execute().data

if fav_data:
    for fav in fav_data:
        st.sidebar.markdown(f"[{fav['rezept_name']}]({fav['url']})")
        if st.sidebar.button(f"🗑️ Löschen", key=f"del_{fav['id']}"):
            supabase.table("favoriten").delete().eq("id", fav['id']).execute()
            st.rerun()
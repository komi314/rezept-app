import streamlit as st
from supabase import create_client, Client
import requests
import random
import json

# --- SUPABASE CLIENT & KONFIGURATION ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- USER-ID ---
user_id = "gast_user"
st.write(f"Eingeloggt als: {user_id}")

# Verlauf der bereits gesehenen URLs initialisieren
if 'seen_recipes' not in st.session_state:
    st.session_state.seen_recipes = set()

def fetch_chefkoch_recipe(is_veg):
    # Nutzen wir die offizielle JSON-API-Suche von Chefkoch, die extrem zuverlässig ist
    # Wir suchen nach einem allgemeinen Begriff oder variieren ihn leicht
    suchbegriffe = ["schnell", "einfach", "leckere", "gesund", "pasta", "pfanne", "kartoffel", "gemüse"]
    query = random.choice(suchbegriffe)
    if is_veg:
        query += " vegetarisch"
        
    api_url = f"https://api.chefkoch.de/v2/recipes?query={query}&limit=30"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            st.warning(f"Chefkoch API hat Code {response.status_code} geliefert.")
            return None
            
        data = response.json()
        results = data.get("results", [])
        
        # Durchmischen, damit es jedes Mal andere Rezepte gibt
        random.shuffle(results)
        
        for item in results:
            recipe_meta = item.get("recipe", {})
            recipe_id = recipe_meta.get("id")
            name = recipe_meta.get("title")
            url = recipe_meta.get("siteUrl")
            
            if not recipe_id or not url or url in st.session_state.seen_recipes:
                continue
                
            # Detaillierte Rezept-Infos abrufen (für die Zutaten)
            detail_url = f"https://api.chefkoch.de/v2/recipes/{recipe_id}"
            detail_resp = requests.get(detail_url, headers=headers)
            
            if detail_resp.status_code != 200:
                continue
                
            detail_data = detail_resp.json()
            ingredients_groups = detail_data.get("ingredients", [])
            
            zutaten = []
            for group in ingredients_groups:
                for ing in group.get("ingredients", []):
                    # Text-Repräsentation der Zutat zusammenbauen (Menge + Einheit + Name)
                    amount = ing.get("amount", "")
                    unit = ing.get("unit", "")
                    iname = ing.get("name", "")
                    zutaten.append(f"{amount} {unit} {iname}".strip())
                    
            if not name or not zutaten:
                continue
                
            # Strenger Check für vegetarisch (falls API trotz Filter Fleisch liefert)
            if is_veg:
                fleisch_woerter = ["fleisch", "huhn", "hähnchen", "schwein", "rind", "fisch", "speck", "schinken", "wurst", "hackfleisch", "pute", "kalb", "lachs", "thunfisch"]
                if any(wort in name.lower() for wort in fleisch_woerter):
                    continue
            
            # Erfolgreich gefunden -> in Session speichern
            st.session_state.seen_recipes.add(url)
            return {"name": name, "zutaten": zutaten, "url": url}
            
        st.warning("Keine neuen Rezepte gefunden. Bitte versuche es noch einmal.")
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
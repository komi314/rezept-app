import streamlit as st
from supabase import create_client, Client
import requests

# --- SUPABASE CLIENT & KONFIGURATION ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- USER-ID ---
user_id = "gast_user"
st.write(f"Eingeloggt als: {user_id}")

# Verlauf initialisieren
if 'seen_recipes' not in st.session_state:
    st.session_state.seen_recipes = set()

def fetch_random_mealdb_recipe(is_veg):
    # Wir rufen die offizielle, ungesperrte Zufalls-API von TheMealDB auf
    url = "https://www.themealdb.com/api/json/v1/1/random.php"
    
    try:
        # Bis zu 5 Versuche, falls ein vegetarischer Filter aktiv ist und zufällig Fleisch kommt
        for _ in range(5):
            response = requests.get(url)
            if response.status_code != 200:
                continue
                
            data = response.json()
            meal = data.get("meals", [{}])[0]
            
            name = meal.get("strMeal")
            source_url = meal.get("strSource") or "https://www.themealdb.com"
            category = meal.get("strCategory", "")
            
            if not name or name in st.session_state.seen_recipes:
                continue
                
            # Vegetarisch-Check über die Kategorie oder den Namen
            if is_veg and category.lower() in ["beef", "chicken", "pork", "goat", "lamb"]:
                continue
                
            # Zutaten und Mengen sauber aus den 20 möglichen Feldern der API extrahieren
            zutaten = []
            for i in range(1, 21):
                ingredient = meal.get(f"strIngredient{i}")
                measure = meal.get(f"strMeasure{i}")
                
                if ingredient and ingredient.strip():
                    zutat_str = f"{measure.strip()} {ingredient.strip()}" if measure else ingredient.strip()
                    zutaten.append(zutat_str)
                    
            st.session_state.seen_recipes.add(name)
            return {"name": name, "zutaten": zutaten, "url": source_url}
            
        st.warning("Konnte kein passendes Rezept finden.")
    except Exception as e:
        st.error(f"Fehler beim Laden: {e}")
    return None

# --- APP UI ---
st.title("👨‍🍳 Smart Recipe App (Random)")
veg_choice = st.radio("Ernährungsweise:", ["Vegetarisch", "Mit Fleisch"], key="veg_radio")

if st.button("Neues Zufalls-Rezept suchen", key="btn_suche"):
    st.session_state.current_recipe = fetch_random_mealdb_recipe(veg_choice == "Vegetarisch")

if 'current_recipe' in st.session_state and st.session_state.current_recipe:
    r = st.session_state.current_recipe
    st.subheader(r["name"])
    st.write("Zutaten:", r["zutaten"])
    st.link_button("Zum Rezept", r["url"])
    
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

# --- SIDEBAR (Einkaufsliste & Favoriten unverändert) ---
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
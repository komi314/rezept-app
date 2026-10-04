import streamlit as st
from supabase import create_client, Client
import requests

# --- SUPABASE CLIENT & KONFIGURATION ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- AUTHENTIFIZIERUNGS-BEREICH (LOGIN / REGISTRIERUNG) ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("👨‍🍳 Smart Recipe App - Login")
    tab1, tab2 = st.tabs(["Einloggen", "Registrieren"])
    
    with tab1:
        st.subheader("Anmelden")
        login_email = st.text_input("E-Mail", key="login_email")
        login_password = st.text_input("Passwort", type="password", key="login_pass")
        if st.button("Einloggen", key="btn_login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                st.session_state.user = res.user
                st.success("Erfolgreich eingeloggt!")
                st.rerun()
            except Exception as e:
                st.error(f"Fehler beim Login: {e}")
                
    with tab2:
        st.subheader("Neuen Account erstellen")
        reg_email = st.text_input("E-Mail", key="reg_email")
        reg_password = st.text_input("Passwort", type="password", key="reg_pass")
        if st.button("Registrieren", key="btn_reg"):
            try:
                res = supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                st.success("Registrierung erfolgreich! Du kannst dich jetzt einloggen.")
            except Exception as e:
                st.error(f"Fehler bei der Registrierung: {e}")
                
    st.stop("Bitte logge dich ein, um die App zu nutzen.")

# Wenn eingeloggt, holen wir die echte User-ID von Supabase
user_id = st.session_state.user.id

# Logout-Button in der Sidebar
if st.sidebar.button("🚪 Abmelden"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- HAUPTAPP (FÜR EINGELOGGTE NUTZER) ---
st.write(f"Eingeloggt als: {st.session_state.user.email}")

# Verlauf initialisieren
if 'seen_recipes' not in st.session_state:
    st.session_state.seen_recipes = set()

def fetch_random_mealdb_recipe(is_veg):
    url = "https://www.themealdb.com/api/json/v1/1/random.php"
    
    try:
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
                
            if is_veg and category.lower() in ["beef", "chicken", "pork", "goat", "lamb"]:
                continue
                
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
            st.rerun()
            
    with col2:
        if st.button("❤️ Ich mag das!", key="save_fav"):
            supabase.table("favoriten").insert({
                "user_id": user_id,
                "rezept_name": r["name"],
                "url": r["url"],
                "zutaten": r["zutaten"]
            }).execute()
            st.success("Zu Favoriten hinzugefügt!")
            st.rerun()

# --- SIDEBAR: EINKAUFSLISTE (Gefiltert nach eingeloggten User) ---
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

# --- SIDEBAR: FAVORITEN (Gefiltert nach eingeloggten User) ---
st.sidebar.markdown("---")
st.sidebar.title("⭐ Deine Favoriten")
fav_data = supabase.table("favoriten").select("*").eq("user_id", user_id).execute().data

if fav_data:
    for fav in fav_data:
        with st.sidebar.container():
            st.markdown(f"[{fav['rezept_name']}]({fav['url']})")
            
            if st.button("🛒 Zur Einkaufsliste", key=f"add_fav_list_{fav['id']}"):
                zutaten_liste = fav.get('zutaten', [])
                for zutat in zutaten_liste:
                    supabase.table("einkaufsliste").insert({
                        "user_id": user_id,
                        "rezept_name": fav['rezept_name'],
                        "zutat": zutat
                    }).execute()
                st.sidebar.success("Zur Einkaufsliste hinzugefügt!")
                st.rerun()
                
            if st.button(f"🗑️ Löschen", key=f"del_{fav['id']}"):
                supabase.table("favoriten").delete().eq("id", fav['id']).execute()
                st.rerun()
            st.markdown("---")
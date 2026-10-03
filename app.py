import streamlit as st
from supabase import create_client, Client
import feedparser
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
    # Wir nutzen verschiedene offizielle RSS-Feeds von Chefkoch (die blockieren nicht)
    rss_urls = [
        "https://www.chefkoch.de/rs/s0t0/rezepte.rss",
        "https://www.chefkoch.de/rs/s0t8/rezepte.rss", # Schnell
        "https://www.chefkoch.de/rs/s0t3/rezepte.rss"  # Einfach
    ]
    
    feed_url = random.choice(rss_urls)
    
    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries
        
        if not entries:
            st.warning("Der Rezept-Feed konnte momentan nicht geladen werden.")
            return None
            
        random.shuffle(entries)
        
        for entry in entries:
            url = entry.link
            name = entry.title
            
            if not url or not name or url in st.session_state.seen_recipes:
                continue
                
            # Strenger Check für vegetarisch basierend auf dem Titel
            if is_veg:
                fleisch_woerter = ["fleisch", "huhn", "hähnchen", "schwein", "rind", "fisch", "speck", "schinken", "wurst", "hackfleisch", "pute", "kalb", "lachs", "thunfisch"]
                if any(wort in name.lower() for wort in fleisch_woerter):
                    continue
            
            # Da RSS-Feeds keine detaillierte Zutatenliste im Text haben, 
            # nutzen wir die Beschreibung oder holen uns einen Platzhalter, 
            # alternativ parsen wir den RSS-Summary-Text falls vorhanden.
            zutaten_text = entry.get("summary", "Zutaten im Originalrezept einsehbar")
            zutaten = [zutaten_text]
            
            st.session_state.seen_recipes.add(url)
            return {"name": name, "zutaten": zutaten, "url": url}
            
        st.warning("Keine neuen Rezepte im Feed gefunden. Bitte versuche es noch einmal.")
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
    st.write("Zutaten-Hinweis:", r["zutaten"][0])
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
            st.success("Gespeichert!")
            
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
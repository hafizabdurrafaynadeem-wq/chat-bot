"""
Pakistan Weather & History Chatbot
-----------------------------------
A single-file Streamlit app (backend + frontend together).

HOW TO RUN:
    1. Install requirements (see REQUIREMENTS block below), e.g.:
       pip install streamlit google-generativeai requests
    2. Run:
       streamlit run app.py
    3. Paste your free Gemini API key in the sidebar
       (get one at https://aistudio.google.com/apikey)

REQUIREMENTS (also save these three lines as requirements.txt):
    streamlit
    google-generativeai
    requests
"""

import re
import requests
import streamlit as st
import google.generativeai as genai

MODEL_NAME = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Knowledge base: Pakistan history (used as context for the chatbot)
# ---------------------------------------------------------------------------
PAKISTAN_HISTORY = """
- The lands that make up modern Pakistan are home to the Indus Valley
  Civilization (c. 2500-1900 BCE), one of the world's oldest urban
  civilizations, with major sites at Mohenjo-daro and Harappa.
- Over centuries the region was shaped by many rulers and cultures,
  including the Mauryan and Gandhara civilizations, the Ghaznavid and
  Ghurid dynasties, the Delhi Sultanate, and later the Mughal Empire,
  which left a lasting legacy of architecture, language, and culture.
- The British East India Company gradually took control of the region
  through the 18th and 19th centuries, and it became part of British
  India (the British Raj) after 1858.
- The movement for a separate Muslim-majority state grew in the early
  20th century, led by the All-India Muslim League. Muhammad Ali
  Jinnah became its most prominent leader and is regarded as the
  founder of Pakistan (Quaid-e-Azam).
- Pakistan came into existence on 14 August 1947, when British India
  was partitioned into India and Pakistan. Partition caused massive
  population movements and communal violence, with millions of people
  displaced.
- Pakistan initially consisted of West Pakistan and East Pakistan
  (separated by Indian territory). Political and economic tensions
  between the two wings, along with a civil war, led to East Pakistan
  becoming the independent country of Bangladesh in 1971.
- Pakistan has had a mix of civilian and military governments since
  independence, including periods of martial law under leaders such
  as Ayub Khan, Zia-ul-Haq, and Pervez Musharraf, alternating with
  periods of parliamentary democracy.
- Pakistan became a nuclear power, conducting nuclear tests in 1998.
- Major cities include Karachi (the largest city and former capital),
  Lahore (a historic cultural capital), and Islamabad (the current
  capital, built in the 1960s).
- Pakistan's culture reflects a blend of its many historical
  influences, with Urdu as the national language and numerous
  regional languages including Punjabi, Sindhi, Pashto, and Balochi.
"""

WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}


# ---------------------------------------------------------------------------
# Backend: live weather lookup (Open-Meteo, free, no API key needed)
# ---------------------------------------------------------------------------
def get_live_weather(city: str):
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "country": "PK"},
            timeout=10,
        ).json()
        if not geo.get("results"):
            geo = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1},
                timeout=10,
            ).json()
        if not geo.get("results"):
            return None

        place = geo["results"][0]
        lat, lon = place["latitude"], place["longitude"]

        wx = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            timeout=10,
        ).json()
        current = wx.get("current_weather")
        if not current:
            return None

        return {
            "place": place.get("name", city),
            "temperature_c": current["temperature"],
            "windspeed_kmh": current["windspeed"],
            "condition": WEATHER_CODES.get(current["weathercode"], "unknown conditions"),
        }
    except Exception:
        return None


def extract_city(text: str) -> str:
    match = re.search(r"(?:in|of|for)\s+([A-Za-z\s]+)", text)
    if match:
        return match.group(1).strip().rstrip("?.!")
    return "Islamabad"


def is_weather_question(text: str) -> bool:
    return any(word in text.lower() for word in ["weather", "temperature", "forecast", "climate today"])


# ---------------------------------------------------------------------------
# Frontend: Streamlit UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Pakistan Weather & History Bot", page_icon="🇵🇰")
st.title("🇵🇰 Pakistan Weather & History Chatbot")
st.caption("Ask about current weather in any Pakistani city, or about Pakistan's history.")

if "messages" not in st.session_state:
    st.session_state.messages = []

st.sidebar.header("🔑 Gemini API Key")
api_key = st.sidebar.text_input(
    "Enter your Google Gemini API key",
    type="password",
    value=st.session_state.get("api_key", ""),
)
if api_key:
    st.session_state.api_key = api_key
st.sidebar.caption("Get a free key at https://aistudio.google.com/apikey")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask about Pakistan's weather or history...")

if user_input:
    if not st.session_state.get("api_key"):
        st.warning("Please enter your Gemini API key in the sidebar first.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Backend: gather context depending on question type
        extra_context = ""
        if is_weather_question(user_input):
            city = extract_city(user_input)
            weather = get_live_weather(city)
            if weather:
                extra_context = (
                    f"LIVE WEATHER DATA for {weather['place']}: "
                    f"{weather['temperature_c']}°C, {weather['condition']}, "
                    f"wind {weather['windspeed_kmh']} km/h. "
                    "Use this real data to answer."
                )
            else:
                extra_context = (
                    f"Could not fetch live weather for '{city}'. "
                    "Tell the user you couldn't find that location's weather."
                )

        try:
            genai.configure(api_key=st.session_state.api_key)
            model = genai.GenerativeModel(
                MODEL_NAME,
                system_instruction=(
                    "You are a friendly assistant specialized in Pakistan's weather "
                    "and history. Use the reference information below when relevant.\n\n"
                    f"PAKISTAN HISTORY REFERENCE:\n{PAKISTAN_HISTORY}\n\n"
                    f"{extra_context}"
                ),
            )
            response = model.generate_content(user_input)
            reply = response.text
        except Exception as e:
            reply = f"⚠️ Error calling Gemini API: {e}"

        st.session_state.messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

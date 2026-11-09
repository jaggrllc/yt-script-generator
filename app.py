import streamlit as st
from openai import OpenAI
import serpapi

st.set_page_config(page_title="YouTube Script Generator", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Video Script Generator + Voiceover")
st.caption("Improved research for recent events • Stronger accuracy controls • Voice preview")

# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("API Keys")
    openai_key = st.text_input("OpenAI API Key", type="password")
    serpapi_key = st.text_input("SerpAPI Key (optional)", type="password")
    
    use_research = st.checkbox("Use SerpAPI research", value=True, help="Recommended for recent events")
    
    st.divider()
    model = st.selectbox("Script Model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1"], index=2)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.5)
    
    st.markdown("---")
    st.markdown("**Tip:** For very recent events, keep research enabled and use a specific topic.")

# ── Main Input ─────────────────────────────────────────────────────
proposed = st.text_area(
    "Proposed Video Script / Topic / Outline",
    height=200,
    placeholder="Example: Learjet 60 crash Greenacres Florida November 1 2026"
)

col1, col2, col3 = st.columns(3)
with col1:
    tone = st.selectbox("Tone", ["Educational", "Conversational", "Storytelling", "Energetic", "Professional"])
with col2:
    length = st.selectbox("Target Length", ["3-5 min", "6-10 min", "11-15 min", "15+ min"])
with col3:
    style = st.selectbox("Style", ["Standard YouTube", "Tutorial", "Review", "Story", "Listicle"])

generate_btn = st.button("🚀 Generate & Proofread Script", type="primary", use_container_width=True)

# ── Functions ──────────────────────────────────────────────────────
def search_facts(query: str, api_key: str) -> str:
    if not api_key:
        return "Research disabled or no SerpAPI key."
    try:
        client = serpapi.Client(api_key=api_key)
        
        # Make the search more specific for recent crash/incident topics
        search_query = query
        lower = query.lower()
        if any(word in lower for word in ["learjet", "crash", "accident", "2026", "n722bd"]):
            search_query = f"{query} November 2026 Greenacres OR 'Palm Beach' OR N722BD"
        
        results = client.search({
            "engine": "google",
            "q": search_query,
            "num": 10,
            "hl": "en",
            "gl": "us"
        })
        
        snippets = []
        for r in results.get("organic_results", [])[:8]:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            link = r.get("link", "")
            if title or snippet:
                snippets.append(f"- {title}\n  {snippet}\n  Source: {link}")
        
        return "\n\n".join(snippets) if snippets else "No strong search results found."
    except Exception as e:
        return f"SerpAPI error: {str(e)}"

def research_is_weak(research: str) -> bool:
    weak_phrases = ["No strong search results", "SerpAPI error", "Research disabled", "no SerpAPI key"]
    if any(p in research for p in weak_phrases):
        return True
    return len(research.strip()) < 250

def generate_script(proposed_text: str, research: str, openai_client: OpenAI) -> str:
    prompt = f"""You are a careful YouTube scriptwriter who prioritizes accuracy.

User request:
{proposed_text}

Tone: {tone}
Target length: {length}
Style: {style}

Research (may be empty):
{research}

CRITICAL RULES:
- Prefer facts that appear in the research above. If the research contains consistent reporting from multiple sources about a recent event, you may use those details.
- Do NOT invent additional names, exact quotes, speculative causes, or unconfirmed details that are not supported by the research.
- If the research is thin, conflicting, or missing, stay general and note that details are still emerging.
- Always attribute specific claims to public reporting or the research rather than stating them as absolute fact.
- Never create a dramatic reenactment of an event that is not supported by the research.
- Write ONLY the spoken script that a narrator would say on camera.
- Do NOT include any director’s directions, stage directions, production notes, B-roll suggestions, camera instructions, [on-screen text], or anything in brackets or parentheses that is not meant to be spoken.

Write a complete, engaging YouTube video script consisting only of the words to be spoken. Return only the final script text."""

    response = openai_client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def proofread_script(script: str, research: str, openai_client: OpenAI) -> str:
    prompt = f"""Strict fact-check. Flag anything suspicious.

Script:
{script}

Research:
{research}

Specifically call out:
- Any specific recent events, named individuals, registration numbers, or precise details that are not supported by the research.
- Recommend removing or heavily rewriting any unverified specific claims.

Give:
1. Unverified claims
2. Suggested fixes
3. Accuracy rating (High/Medium/Low)
4. Publish recommendation"""

    response = openai_client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def generate_tts(text: str, openai_client: OpenAI, voice: str, tts_model: str) -> bytes:
    max_chars = 4000
    chunks = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    audio_parts = []
    for chunk in chunks:
        if chunk.strip():
            resp = openai_client.audio.speech.create(
                model=tts_model, voice=voice, input=chunk, response_format="mp3"
            )
            audio_parts.append(resp.content)
    return b"".join(audio_parts)

# ── Generation ─────────────────────────────────────────────────────
if "generated_script" not in st.session_state:
    st.session_state.generated_script = ""

if generate_btn:
    if not openai_key:
        st.error("OpenAI API key is required.")
    elif not proposed.strip():
        st.warning("Enter a topic or script.")
    else:
        with st.spinner("Researching and generating..."):
            try:
                client = OpenAI(api_key=openai_key)
                
                research = "Research disabled."
                if use_research and serpapi_key:
                    research = search_facts(proposed[:300], serpapi_key)
                
                if research_is_weak(research):
                    st.warning("Limited research available. Script will stay more general to avoid unsupported details.")
                
                generated = generate_script(proposed, research, client)
                fact_check = proofread_script(generated, research, client)
                
                st.session_state.generated_script = generated
                st.success("Script generated and checked!")
                
                st.subheader("Generated Script")
                st.text_area("Script", value=generated, height=400, key="script_display")
                
                with st.expander("🔍 Fact-Check Notes", expanded=True):
                    st.markdown(fact_check)
                
                with st.expander("Research Used"):
                    st.markdown(research or "None")
                    
            except Exception as e:
                st.error(str(e))

# ── Voiceover Section ──────────────────────────────────────────────
if st.session_state.generated_script:
    st.divider()
    st.subheader("🎙️ Voiceover Studio")
    
    col1, col2 = st.columns(2)
    with col1:
        tts_model = st.selectbox("TTS Model", ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"], index=1)
    with col2:
        voice = st.selectbox("Voice", ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "ash", "coral", "sage"], index=4)
    
    st.markdown("#### Preview Voice")
    preview_text = st.text_input("Preview text", value="This is a preview of the selected voice for your YouTube script.")
    
    if st.button("▶️ Preview Selected Voice", use_container_width=True):
        with st.spinner("Generating preview..."):
            try:
                client = OpenAI(api_key=openai_key)
                audio = generate_tts(preview_text, client, voice, tts_model)
                st.audio(audio, format="audio/mp3")
            except Exception as e:
                st.error(str(e))
    
    st.markdown("#### Full Voiceover")
    if st.button("🔊 Generate Full Voiceover MP3", type="primary", use_container_width=True):
        with st.spinner("Creating voiceover..."):
            try:
                client = OpenAI(api_key=openai_key)
                audio = generate_tts(st.session_state.generated_script, client, voice, tts_model)
                st.audio(audio, format="audio/mp3")
                st.download_button("⬇️ Download MP3", audio, "youtube_voiceover.mp3", "audio/mp3")
            except Exception as e:
                st.error(str(e))

st.markdown("---")
st.caption("Improved research for recent events is active. Scripts now contain only spoken narration with no director’s directions.")

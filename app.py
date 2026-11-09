import streamlit as st
from openai import OpenAI
import serpapi

st.set_page_config(page_title="YouTube Script Generator", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Video Script Generator + Voiceover")
st.caption("Stronger accuracy controls • Optional research • Voice preview")

# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("API Keys")
    openai_key = st.text_input("OpenAI API Key", type="password")
    serpapi_key = st.text_input("SerpAPI Key (optional)", type="password")
    
    use_research = st.checkbox("Use SerpAPI research", value=True, help="Uncheck to disable research and reduce hallucination risk on recent events")
    
    st.divider()
    model = st.selectbox("Script Model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1"], index=0)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.5)  # lowered default
    
    st.markdown("---")
    st.markdown("**Safety note:** For very recent events, leave research on and verify the fact-check carefully.")

# ── Main Input ─────────────────────────────────────────────────────
proposed = st.text_area(
    "Proposed Video Script / Topic / Outline",
    height=200,
    placeholder="Enter topic or draft..."
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
        results = client.search({"engine": "google", "q": query, "num": 8, "hl": "en"})
        snippets = []
        for r in results.get("organic_results", [])[:6]:
            snippets.append(f"- {r.get('title', '')}: {r.get('snippet', '')}")
        return "\n".join(snippets) if snippets else "No strong search results found."
    except Exception as e:
        return f"SerpAPI error: {str(e)}"

def research_is_weak(research: str) -> bool:
    weak_phrases = ["No strong search results", "SerpAPI error", "Research disabled", "no SerpAPI key"]
    if any(p in research for p in weak_phrases):
        return True
    return len(research.strip()) < 200

def generate_script(proposed_text: str, research: str, openai_client: OpenAI) -> str:
    prompt = f"""You are a careful YouTube scriptwriter who refuses to hallucinate.

User request:
{proposed_text}

Tone: {tone}
Target length: {length}
Style: {style}

Research (may be empty):
{research}

CRITICAL RULES — DO NOT BREAK THESE:
- Never invent specific real-world events that happened in 2025 or 2026 (or any very recent date).
- Never invent names of people, aircraft registration numbers, exact dates, flight numbers, or official investigations unless they appear clearly in the research above.
- If the topic appears to be about a specific recent incident and the research does not confirm it, do NOT write a dramatic reenactment. Instead write a short note saying the event could not be verified and offer a general educational script on the broader topic instead.
- Prefer general, educational, or clearly hypothetical content when research is weak.

Write the script (or the verification note + safe alternative). Return only the final text."""

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
- Any specific recent (2025–2026) events, crashes, or named individuals that are not supported by the research.
- Aircraft registration numbers or precise details that appear invented.
- Recommend removing or heavily rewriting any unverified specific incident.

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
        with st.spinner("Generating..."):
            try:
                client = OpenAI(api_key=openai_key)
                
                research = "Research disabled."
                if use_research and serpapi_key:
                    research = search_facts(proposed[:250], serpapi_key)
                
                if research_is_weak(research):
                    st.warning("Limited or no research available. Script will avoid specific recent events and named individuals.")
                
                generated = generate_script(proposed, research, client)
                fact_check = proofread_script(generated, research, client)
                
                st.session_state.generated_script = generated
                st.success("Done")
                
                st.subheader("Generated Script")
                st.text_area("Script", value=generated, height=400, key="script_display")
                
                with st.expander("🔍 Fact-Check Notes", expanded=True):
                    st.markdown(fact_check)
                
                with st.expander("Research Used"):
                    st.markdown(research or "None")
                    
            except Exception as e:
                st.error(str(e))

# ── Voiceover Section (unchanged from previous) ────────────────────
if st.session_state.generated_script:
    st.divider()
    st.subheader("🎙️ Voiceover Studio")
    
    col1, col2 = st.columns(2)
    with col1:
        tts_model = st.selectbox("TTS Model", ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"], index=1)
    with col2:
        voice = st.selectbox("Voice", ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "ash", "coral", "sage"], index=4)
    
    st.markdown("#### Preview Voice")
    preview_text = st.text_input("Preview text", value="This is a preview of the selected voice.")
    
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
st.caption("SerpAPI can be turned off in the sidebar. Stronger anti-hallucination rules are active.")

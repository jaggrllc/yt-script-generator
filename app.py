import streamlit as st
from openai import OpenAI
import serpapi
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import io

st.set_page_config(page_title="YouTube Script Generator", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Video Script Generator + Voiceover")
st.caption("News Narrator / Classic Trailer styles • Custom name intro • Auto normalize")

# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("API Keys")
    openai_key = st.text_input("OpenAI API Key", type="password")
    serpapi_key = st.text_input("SerpAPI Key (optional)", type="password")
    
    use_research = st.checkbox("Use SerpAPI research", value=True)
    
    st.divider()
    model = st.selectbox("Script Model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1"], index=2)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.5)

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
        lower = query.lower()
        search_query = query
        if any(word in lower for word in ["learjet", "crash", "accident", "2026", "n722bd", "greenacres"]):
            search_query = (
                f"{query} November 2026 "
                f"-site:facebook.com -site:instagram.com -site:twitter.com -site:x.com -site:tiktok.com "
                f"(site:cnn.com OR site:bbc.com OR site:reuters.com OR site:apnews.com OR "
                f"site:wikipedia.org OR site:ntsb.gov OR site:faa.gov OR site:aviation-safety.net)"
            )
        results = client.search({"engine": "google", "q": search_query, "num": 12, "hl": "en", "gl": "us"})
        snippets = []
        for r in results.get("organic_results", [])[:10]:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            link = r.get("link", "")
            if any(d in link.lower() for d in ["facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com"]):
                continue
            if title or snippet:
                snippets.append(f"- {title}\n  {snippet}\n  Source: {link}")
        return "\n\n".join(snippets) if snippets else "No strong search results found."
    except Exception as e:
        return f"SerpAPI error: {str(e)}"

def research_is_weak(research: str) -> bool:
    weak = ["No strong search results", "SerpAPI error", "Research disabled", "no SerpAPI key"]
    return any(p in research for p in weak) or len(research.strip()) < 250

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
- Prefer facts that appear in the research above.
- Do NOT invent unsupported details.
- Write ONLY the spoken script. No director’s directions, stage directions, or production notes.
Return only the final spoken script text."""
    response = openai_client.chat.completions.create(
        model=model, temperature=temperature,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def proofread_script(script: str, research: str, openai_client: OpenAI) -> str:
    prompt = f"""Strict fact-check the following script against the research.

Script:
{script}

Research:
{research}

Provide:
1. Unverified claims
2. Suggested fixes
3. Accuracy rating (High/Medium/Low)
4. Publish recommendation"""
    response = openai_client.chat.completions.create(
        model=model, temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def process_audio(audio_bytes: bytes, style: str) -> bytes:
    """Apply pitch shift (Classic Trailer) + light processing + always normalize."""
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    
    if style == "Classic Trailer":
        new_sample_rate = int(audio.frame_rate * 0.89)
        audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_sample_rate})
        audio = audio.set_frame_rate(44100)
    
    try:
        audio = compress_dynamic_range(audio, threshold=-18.0, ratio=3.0, attack=5.0, release=50.0)
    except Exception:
        pass
    
    audio = normalize(audio)
    
    buffer = io.BytesIO()
    audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

def generate_tts(text: str, openai_client: OpenAI, voice: str, tts_model: str, style: str, narrator_name: str) -> bytes:
    instructions = None
    if tts_model == "gpt-4o-mini-tts":
        name_intro = ""
        if narrator_name.strip():
            name_intro = f" At the very beginning, briefly introduce yourself by saying something like 'I'm {narrator_name}.' Then continue with the script."
        
        if style == "News Narrator":
            instructions = f"Speak in a clear, professional, neutral news-anchor style. Moderate pace, authoritative but calm and natural.{name_intro}"
        elif style == "Classic Trailer":
            instructions = f"Speak in a deep, dramatic, cinematic movie-trailer narrator style. Low, resonant, powerful delivery with deliberate pacing.{name_intro}"
    
    max_chars = 4000
    chunks = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    audio_parts = []
    
    for chunk in chunks:
        if chunk.strip():
            kwargs = {"model": tts_model, "voice": voice, "input": chunk, "response_format": "mp3"}
            if instructions:
                kwargs["instructions"] = instructions
            resp = openai_client.audio.speech.create(**kwargs)
            audio_parts.append(resp.content)
    
    combined = b"".join(audio_parts)
    return process_audio(combined, style)

# ── Session State ──────────────────────────────────────────────────
if "generated_script" not in st.session_state:
    st.session_state.generated_script = ""
if "voiceover_audio" not in st.session_state:
    st.session_state.voiceover_audio = None

# ── Generation ─────────────────────────────────────────────────────
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
                    st.warning("Limited research available. Script will stay more general.")
                
                generated = generate_script(proposed, research, client)
                fact_check = proofread_script(generated, research, client)
                
                st.session_state.generated_script = generated
                st.session_state.voiceover_audio = None
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
    
    col1, col2, col3 = st.columns(3)
    with col1:
        tts_model = st.selectbox("TTS Model", ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"], index=2)
    with col2:
        base_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "ash", "coral", "sage"]
        extra_voices = ["ballad", "verse", "marin", "cedar"]
        available_voices = base_voices + extra_voices if tts_model == "gpt-4o-mini-tts" else base_voices
        voice = st.selectbox("Voice", available_voices, index=available_voices.index("onyx") if "onyx" in available_voices else 0)
    with col3:
        voice_style = st.selectbox("Voice Style", ["News Narrator", "Classic Trailer"], index=0)
    
    narrator_name = st.text_input(
        "Custom Narrator Name (optional)",
        placeholder="e.g. Alex Rivera, Captain James, or leave blank",
        help="If filled, the voice will introduce itself by this name at the start (works best with gpt-4o-mini-tts)."
    )
    
    st.markdown("#### Preview Voice")
    preview_text = st.text_input("Preview text", value="This is a preview of the selected voice and style.")
    
    if st.button("▶️ Preview Selected Voice", use_container_width=True):
        with st.spinner("Generating preview..."):
            try:
                client = OpenAI(api_key=openai_key)
                audio = generate_tts(preview_text, client, voice, tts_model, voice_style, narrator_name)
                st.audio(audio, format="audio/mp3")
            except Exception as e:
                st.error(str(e))
    
    st.markdown("#### Full Voiceover")
    if st.button("🔊 Generate Full Voiceover MP3", type="primary", use_container_width=True):
        with st.spinner("Creating and processing voiceover..."):
            try:
                client = OpenAI(api_key=openai_key)
                audio = generate_tts(st.session_state.generated_script, client, voice, tts_model, voice_style, narrator_name)
                st.session_state.voiceover_audio = audio
                st.success("Voiceover generated, processed, and normalized!")
                st.audio(audio, format="audio/mp3")
            except Exception as e:
                st.error(str(e))
    
    if st.session_state.voiceover_audio is not None:
        st.download_button(
            label="⬇️ Download MP3 Voiceover",
            data=st.session_state.voiceover_audio,
            file_name="youtube_voiceover.mp3",
            mime="audio/mp3",
            use_container_width=True
        )

st.markdown("---")
st.caption("Enter a custom narrator name to have the voice introduce itself. All audio is normalized. Classic Trailer style applies a deeper pitch.")

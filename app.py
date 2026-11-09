import streamlit as st
from openai import OpenAI
import serpapi

st.set_page_config(page_title="YouTube Script Generator", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Video Script Generator + Voiceover")
st.caption("Generate accurate scripts, fact-check them, preview voices, and create natural AI voiceovers")

# ── Sidebar: API Keys ──────────────────────────────────────────────
with st.sidebar:
    st.header("API Keys")
    openai_key = st.text_input("OpenAI API Key", type="password", help="sk-...")
    serpapi_key = st.text_input("SerpAPI Key", type="password", help="From serpapi.com")
    
    st.divider()
    model = st.selectbox("Script Model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1"], index=0)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.7)
    
    st.markdown("---")
    st.markdown("**How to use**")
    st.markdown("1. Paste topic or draft")
    st.markdown("2. Generate script")
    st.markdown("3. Review fact-check")
    st.markdown("4. Preview voices → generate full MP3")

# ── Main Input ─────────────────────────────────────────────────────
proposed = st.text_area(
    "Proposed Video Script / Topic / Outline",
    height=200,
    placeholder="Paste your draft script, outline, or just the video topic here..."
)

col1, col2, col3 = st.columns(3)
with col1:
    tone = st.selectbox("Tone", ["Educational", "Conversational", "Storytelling", "Energetic", "Professional"])
with col2:
    length = st.selectbox("Target Length", ["3-5 min", "6-10 min", "11-15 min", "15+ min"])
with col3:
    style = st.selectbox("Style", ["Standard YouTube", "Tutorial", "Review", "Story", "Listicle"])

generate_btn = st.button("🚀 Generate & Proofread Script", type="primary", use_container_width=True)

# ── Helper Functions ───────────────────────────────────────────────
def search_facts(query: str, api_key: str) -> str:
    try:
        client = serpapi.Client(api_key=api_key)
        results = client.search({
            "engine": "google",
            "q": query,
            "num": 8,
            "hl": "en"
        })
        snippets = []
        for r in results.get("organic_results", [])[:6]:
            snippets.append(f"- {r.get('title', '')}: {r.get('snippet', '')}")
        return "\n".join(snippets) if snippets else "No strong search results found."
    except Exception as e:
        return f"SerpAPI error: {str(e)}"

def research_is_weak(research: str) -> bool:
    """Returns True if research is too thin to support specific claims."""
    if not research or "SerpAPI error" in research or "No strong search results" in research:
        return True
    return len(research.strip()) < 150

def generate_script(proposed_text: str, research: str, openai_client: OpenAI) -> str:
    prompt = f"""You are a careful YouTube scriptwriter who prioritizes accuracy.

User input (topic, outline, or draft):
{proposed_text}

Tone: {tone}
Target length: {length}
Style: {style}

Real-time research (from Google via SerpAPI):
{research}

STRICT RULES:
- Do NOT invent specific real-world events, accidents, deaths, named individuals, exact dates, flight numbers, or official investigations unless they are clearly supported by the research above.
- If the research does not contain concrete facts about a specific incident, treat the topic as general or educational. Do not create a fictional tragedy and present it as real.
- Prefer well-established public knowledge or clearly label speculative/hypothetical sections.
- If you must mention an event that is not in the research, explicitly say “according to reports” or “unconfirmed” — or better, avoid it.

Write a complete, engaging YouTube video script that:
- Has a strong hook in the first 15 seconds
- Clear structure (Hook → Intro → Main Points → CTA)
- Natural spoken language
- Stays grounded in the provided research

Return ONLY the script text."""

    response = openai_client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def proofread_script(script: str, research: str, openai_client: OpenAI) -> str:
    prompt = f"""You are a strict fact-checker. Analyze this YouTube script against the research data.

Script:
{script}

Research data:
{research}

Rules:
- Flag any specific real-world claims (named people, exact dates, accident details, official investigations, numbers) that are NOT supported by the research.
- A future or very recent date with no supporting research should be treated as highly suspicious.
- Do not assume the model’s internal knowledge is reliable for recent events.

Provide:
1. List of unverified or potentially fabricated claims (be specific)
2. Suggested safe rewrites or removals
3. Overall Accuracy Rating: High / Medium / Low
4. Recommendation: “Safe to publish” or “Needs major revision / more research”

Be direct and practical."""

    response = openai_client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def generate_tts(text: str, openai_client: OpenAI, voice: str, tts_model: str) -> bytes:
    """Generate TTS audio. Handles long text by chunking."""
    max_chars = 4000
    chunks = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    
    audio_parts = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        response = openai_client.audio.speech.create(
            model=tts_model,
            voice=voice,
            input=chunk,
            response_format="mp3"
        )
        audio_parts.append(response.content)
    
    return b"".join(audio_parts)

# ── Run Generation ─────────────────────────────────────────────────
if "generated_script" not in st.session_state:
    st.session_state.generated_script = ""

if generate_btn:
    if not openai_key or not serpapi_key:
        st.error("Please enter both API keys in the sidebar.")
    elif not proposed.strip():
        st.warning("Please enter a topic or proposed script.")
    else:
        with st.spinner("Researching with SerpAPI + generating with OpenAI..."):
            try:
                client = OpenAI(api_key=openai_key)
                
                research = search_facts(proposed[:200], serpapi_key)
                
                # Warn if research is weak
                if research_is_weak(research):
                    st.warning("Research results are limited. The script will stay general to avoid inventing specific events.")
                
                generated = generate_script(proposed, research, client)
                fact_check = proofread_script(generated, research, client)
                
                st.session_state.generated_script = generated
                st.success("Script generated and checked!")
                
                st.subheader("Generated YouTube Video Script")
                st.text_area(
                    "Generated Script (copy this)",
                    value=generated,
                    height=400,
                    key="generated_script_display"
                )
                
                with st.expander("🔍 Fact-Check & Proofreading Notes", expanded=True):
                    st.markdown(fact_check)
                
                with st.expander("Research Sources Used"):
                    st.markdown(research)
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.info("Check your API keys and try again.")

# ── Voiceover Section (with Preview) ───────────────────────────────
if st.session_state.generated_script:
    st.divider()
    st.subheader("🎙️ Voiceover Studio")
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        tts_model = st.selectbox(
            "TTS Model",
            ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"],
            index=1,
            help="tts-1-hd = higher quality • gpt-4o-mini-tts = more controllable"
        )
    with col_v2:
        voice = st.selectbox(
            "Voice",
            ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "ash", "coral", "sage"],
            index=4
        )
    
    # ── Voice Preview ──────────────────────────────────────────────
    st.markdown("#### Preview Voice")
    preview_text = st.text_input(
        "Preview text",
        value="This is a preview of the selected voice for your YouTube script. How does it sound?",
        help="Short sample to test the voice before generating the full audio"
    )
    
    if st.button("▶️ Preview Selected Voice", use_container_width=True):
        if not preview_text.strip():
            st.warning("Enter some preview text.")
        else:
            with st.spinner("Generating preview..."):
                try:
                    client = OpenAI(api_key=openai_key)
                    preview_audio = generate_tts(preview_text, client, voice, tts_model)
                    st.audio(preview_audio, format="audio/mp3")
                    st.caption(f"Preview using **{voice}** voice")
                except Exception as e:
                    st.error(f"Preview error: {str(e)}")
    
    st.markdown("---")
    
    # ── Full Voiceover Generation ──────────────────────────────────
    st.markdown("#### Full Script Voiceover")
    if st.button("🔊 Generate Full Voiceover MP3", type="primary", use_container_width=True):
        with st.spinner("Creating full voiceover (this may take a moment for long scripts)..."):
            try:
                client = OpenAI(api_key=openai_key)
                audio_bytes = generate_tts(
                    st.session_state.generated_script,
                    client,
                    voice,
                    tts_model
                )
                
                st.audio(audio_bytes, format="audio/mp3")
                
                st.download_button(
                    label="⬇️ Download Full Voiceover (MP3)",
                    data=audio_bytes,
                    file_name="youtube_voiceover.mp3",
                    mime="audio/mp3"
                )
                st.success("Full voiceover ready!")
                
            except Exception as e:
                st.error(f"TTS Error: {str(e)}")
                st.info("Make sure your OpenAI key has TTS access.")

st.markdown("---")
st.caption("Stronger accuracy controls active • Preview voices before generating the full MP3.")

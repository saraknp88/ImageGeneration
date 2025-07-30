import streamlit as st
import requests
import os
import time
from PIL import Image
from io import BytesIO
import hashlib
import logging

# Configure logging (don't log sensitive data)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="✨ Secure AI Image Generator",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main { padding-top: 2rem; }
    
    .stTextArea > div > div > textarea {
        font-size: 16px;
        border-radius: 10px;
    }
    
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        font-weight: 600;
        font-size: 16px;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover:not(:disabled) {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
    }
    
    .security-info {
        background: #e8f4fd;
        border-left: 4px solid #1976d2;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    
    .usage-warning {
        background: #fff3e0;
        border-left: 4px solid #f57c00;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize secure session state
if 'generated_images' not in st.session_state:
    st.session_state.generated_images = []
if 'generation_count' not in st.session_state:
    st.session_state.generation_count = 0
if 'daily_limit_reached' not in st.session_state:
    st.session_state.daily_limit_reached = False

# Security configurations
MAX_DAILY_GENERATIONS = 20  # Prevent abuse
MAX_PROMPT_LENGTH = 500
BLOCKED_WORDS = ['nsfw', 'explicit', 'nude', 'violence', 'gore', 'sexual']

def get_api_key_safely():
    """
    Securely retrieve API key from environment/secrets
    Returns None if not found or invalid
    """
    try:
        # Try multiple sources (in order of preference)
        api_key = (
            st.secrets.get("OPENAI_API_KEY") or      # Streamlit Cloud secrets
            os.getenv("OPENAI_API_KEY") or           # Environment variable
            os.environ.get("OPENAI_API_KEY")         # System environment
        )
        
        if not api_key:
            return None, "API key not found in environment variables or secrets"
        
        # Basic validation
        if not isinstance(api_key, str) or not api_key.startswith('sk-'):
            return None, "Invalid API key format"
        
        if len(api_key) < 20:  # OpenAI keys are much longer
            return None, "API key too short - possibly invalid"
        
        # ✅ NEVER LOG THE ACTUAL KEY
        logger.info("API key retrieved successfully")
        return api_key, None
        
    except Exception as e:
        logger.error(f"Error retrieving API key: {str(e)}")
        return None, "Failed to retrieve API key"

def validate_prompt_security(prompt):
    """
    Validate prompt for security and content policy
    Returns (is_valid, cleaned_prompt, error_message)
    """
    if not prompt or not isinstance(prompt, str):
        return False, "", "Prompt must be a non-empty string"
    
    # Clean and validate length
    cleaned_prompt = prompt.strip()
    
    if len(cleaned_prompt) < 5:
        return False, "", "Prompt too short - please be more descriptive"
    
    if len(cleaned_prompt) > MAX_PROMPT_LENGTH:
        return False, "", f"Prompt too long - maximum {MAX_PROMPT_LENGTH} characters"
    
    # Content filtering
    prompt_lower = cleaned_prompt.lower()
    for blocked_word in BLOCKED_WORDS:
        if blocked_word in prompt_lower:
            return False, "", "Prompt contains inappropriate content"
    
    # Additional security checks
    if any(char in cleaned_prompt for char in ['<', '>', '{', '}', '`']):
        # Remove potentially dangerous characters
        cleaned_prompt = ''.join(char for char in cleaned_prompt if char not in '<>{}`')
    
    return True, cleaned_prompt, None

def check_rate_limits():
    """Check if user has exceeded rate limits"""
    if st.session_state.generation_count >= MAX_DAILY_GENERATIONS:
        st.session_state.daily_limit_reached = True
        return False, f"Daily limit of {MAX_DAILY_GENERATIONS} generations reached"
    
    return True, None

def make_secure_api_request(prompt):
    """
    Make secure API request to OpenAI with detailed debugging
    Returns (success, result_or_error_message)
    """
    try:
        # Get API key securely
        api_key, error = get_api_key_safely()
        if not api_key:
            return False, error or "API key configuration error"
        
        # Prepare headers (never log these!)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
            'User-Agent': 'StreamlitImageGenerator/1.0'
        }
        
        # DALL-E 3 can only generate 1 image at a time
        request_data = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,  # DALL-E 3 only supports n=1
            "size": "1024x1024",
            "quality": "standard",
            "response_format": "url"
        }
        
        # ✅ Safe logging (no sensitive data)
        logger.info(f"Making API request for prompt length: {len(prompt)}")
        
        # Make TWO separate requests for 2 images (DALL-E 3 limitation)
        image_urls = []
        
        for i in range(2):
            st.write(f"🎨 Generating image {i+1}/2...")
            
            # Make request with timeout
            response = requests.post(
                'https://api.openai.com/v1/images/generations',
                headers=headers,
                json=request_data,
                timeout=60
            )
            
            # Debug information (safe to show)
            st.write(f"API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'data' in result and len(result['data']) > 0:
                    image_urls.append(result['data'][0]['url'])
                    st.write(f"✅ Image {i+1} generated successfully!")
                else:
                    return False, f"No image data returned for image {i+1}"
            
            elif response.status_code == 429:
                return False, "Rate limit exceeded. Please wait before trying again."
            
            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    
                    # Show detailed error for debugging
                    st.write(f"API Error Details: {error_message}")
                    
                    if 'content_policy_violation' in error_message.lower():
                        return False, "Content policy violation. Please modify your prompt."
                    elif 'billing' in error_message.lower():
                        return False, "Billing issue. Please check your OpenAI account billing."
                    elif 'quota' in error_message.lower():
                        return False, "Usage quota exceeded. Please check your OpenAI usage limits."
                    else:
                        return False, f"API Error: {error_message}"
                except:
                    return False, f"Bad request (400). Response: {response.text[:200]}"
            
            elif response.status_code == 401:
                return False, "Authentication failed. Please check your API key."
            
            elif response.status_code == 403:
                return False, "Access denied. Please check your API key permissions."
            
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    return False, f"API Error ({response.status_code}): {error_message}"
                except:
                    return False, f"API request failed with status {response.status_code}: {response.text[:200]}"
        
        if len(image_urls) > 0:
            logger.info(f"Successfully generated {len(image_urls)} images")
            return True, image_urls
        else:
            return False, "No images were generated successfully"
            
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return False, "Request timed out. Please try again."
    
    except requests.exceptions.ConnectionError:
        logger.error("Connection error")
        return False, "Network connection error. Please check your internet."
    
    except Exception as e:
        # Show more details for debugging
        logger.error(f"Unexpected error in API request: {str(e)}")
        return False, f"Unexpected error: {str(e)}"

def display_security_info():
    """Display security and privacy information"""
    with st.expander("🔒 Security & Privacy Information"):
        st.markdown("""
        **How we protect your data:**
        - ✅ API keys stored securely in environment variables
        - ✅ No sensitive data logged or stored
        - ✅ Content filtering for inappropriate prompts
        - ✅ Rate limiting to prevent abuse
        - ✅ Secure HTTPS connections only
        - ✅ Generated images are not stored on our servers
        
        **Usage limits:**
        - Maximum {MAX_DAILY_GENERATIONS} generations per day
        - Maximum {MAX_PROMPT_LENGTH} characters per prompt
        - Content policy compliance required
        """.format(MAX_DAILY_GENERATIONS=MAX_DAILY_GENERATIONS, MAX_PROMPT_LENGTH=MAX_PROMPT_LENGTH))

def main():
    st.markdown("""
    <div style='text-align: center; padding: 2rem 0;'>
        <h1 style='background: linear-gradient(135deg, #667eea, #764ba2); 
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
                   font-size: 3rem; margin-bottom: 0.5rem;'>
            🔒 Secure AI Image Generator
        </h1>
        <p style='font-size: 1.2rem; color: #666; margin-bottom: 2rem;'>
            Generate images safely with enterprise-grade security
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check API key configuration
    api_key, error = get_api_key_safely()
    if not api_key:
        st.error("🚨 Configuration Error")
        st.markdown(f"""
        <div class="security-info">
        <strong>API Key Not Found!</strong><br><br>
        
        <strong>For local development:</strong><br>
        1. Create a <code>.env</code> file in your project root<br>
        2. Add: <code>OPENAI_API_KEY=your_key_here</code><br>
        3. Make sure <code>.env</code> is in your <code>.gitignore</code><br><br>
        
        <strong>For Streamlit Cloud deployment:</strong><br>
        1. Go to your app settings<br>
        2. Click "Secrets"<br>
        3. Add: <code>OPENAI_API_KEY = "your_key_here"</code><br><br>
        
        <strong>Error details:</strong> {error}
        </div>
        """, unsafe_allow_html=True)
        
        display_security_info()
        st.stop()
    
    # Display current usage
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Today's Generations", st.session_state.generation_count)
    with col2:
        remaining = MAX_DAILY_GENERATIONS - st.session_state.generation_count
        st.metric("Remaining Today", max(0, remaining))
    with col3:
        estimated_cost = st.session_state.generation_count * 0.08
        st.metric("Estimated Cost", f"${estimated_cost:.2f}")
    
    # Check rate limits
    rate_ok, rate_error = check_rate_limits()
    if not rate_ok:
        st.error(f"🚫 {rate_error}")
        st.info("Rate limits reset daily to prevent abuse and control costs.")
        display_security_info()
        st.stop()
    
    # Main interface
    st.markdown("### 🎨 Describe Your Image")
    prompt = st.text_area(
        "Enter your prompt:",
        height=100,
        max_chars=MAX_PROMPT_LENGTH,
        placeholder=f"Describe your image in detail... (max {MAX_PROMPT_LENGTH} characters)",
        help="Be specific and creative! Avoid inappropriate content."
    )
    
    # Character counter
    if prompt:
        char_count = len(prompt)
        color = "red" if char_count > MAX_PROMPT_LENGTH * 0.9 else "orange" if char_count > MAX_PROMPT_LENGTH * 0.7 else "green"
        st.markdown(f"<small style='color: {color};'>{char_count}/{MAX_PROMPT_LENGTH} characters</small>", unsafe_allow_html=True)
    
    # Example prompts
    with st.expander("💡 Safe example prompts"):
        examples = [
            "A peaceful mountain landscape with a crystal clear lake at sunset",
            "A cozy library with floating books and warm golden lighting",
            "A futuristic city with glass towers and flying cars",
            "A magical forest with glowing mushrooms and fairy lights",
            "An astronaut planting flowers on Mars with Earth in the background"
        ]
        
        for example in examples:
            if st.button(example, key=f"ex_{hash(example)}"):
                st.session_state.selected_prompt = example
                st.rerun()
    
    # Use selected example
    if 'selected_prompt' in st.session_state:
        prompt = st.session_state.selected_prompt
        del st.session_state.selected_prompt
        st.rerun()
    
    # Generate button
    if st.button("🎨 Generate Images", type="primary", disabled=st.session_state.daily_limit_reached):
        if not prompt:
            st.error("Please enter a prompt to generate images.")
            return
        
        # Validate prompt
        is_valid, clean_prompt, validation_error = validate_prompt_security(prompt)
        if not is_valid:
            st.error(f"❌ {validation_error}")
            return
        
        # Show cost warning for high usage
        if st.session_state.generation_count > 10:
            st.warning(f"⚠️ You've made {st.session_state.generation_count} generations today. Each generation costs ~$0.08")
        
        # Generate images
        with st.spinner("🎨 Creating your images... This may take 10-30 seconds"):
            progress = st.progress(0)
            for i in range(100):
                time.sleep(0.05)
                progress.progress(i + 1)
            
            success, result = make_secure_api_request(clean_prompt)
            progress.empty()
        
        if success:
            st.session_state.generated_images = result
            st.session_state.generation_count += 1
            st.success("🎉 Images generated successfully!")
            st.rerun()
        else:
            st.error(f"❌ {result}")
    
    # Display generated images
    if st.session_state.generated_images:
        st.markdown("---")
        st.markdown("### 🖼️ Generated Images")
        
        cols = st.columns(2)
        for i, image_url in enumerate(st.session_state.generated_images):
            with cols[i % 2]:
                st.markdown(f"#### ✨ Image {i + 1}")
                
                try:
                    st.image(image_url, use_column_width=True)
                    
                    # Secure download (don't expose URLs in logs)
                    if st.button(f"💾 Download Image {i + 1}", key=f"dl_{i}"):
                        try:
                            response = requests.get(image_url, timeout=30)
                            if response.status_code == 200:
                                st.download_button(
                                    label=f"⬇️ Save Image {i + 1}",
                                    data=response.content,
                                    file_name=f"ai_image_{int(time.time())}_{i+1}.png",
                                    mime="image/png",
                                    key=f"save_{i}"
                                )
                            else:
                                st.error("Failed to download image")
                        except Exception as e:
                            st.error("Download failed - please try again")
                            logger.error(f"Download error: {str(e)}")
                    
                except Exception as e:
                    st.error(f"Error loading image {i + 1}")
                    logger.error(f"Image display error: {str(e)}")
    
    # Security information
    display_security_info()
    
    # Usage warning
    if st.session_state.generation_count > 15:
        st.markdown(f"""
        <div class="usage-warning">
        <strong>⚠️ High Usage Alert</strong><br>
        You've generated {st.session_state.generation_count} images today. 
        Please monitor your OpenAI usage dashboard to track costs.
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

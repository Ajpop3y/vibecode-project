import time
import os
import sys
import shutil
from fpdf import FPDF

# Ensure we can import from src
sys.path.insert(0, os.path.abspath("src"))

try:
    from vibecode.renderers.llm import LLMRenderer, FONT_PATH
    from vibecode.renderers.human import HumanRenderer
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Could not import vibecode modules.")
    print(f"   Ensure you are running this from the project root.")
    print(f"   Error details: {e}")
    sys.exit(1)

def test_llm_renderer():
    print("\n[1/2] Testing LLM Renderer (Auto-Healing Font)...")
    
    # Check if font exists before run
    font_existed_before = os.path.exists(FONT_PATH)
    
    if not font_existed_before:
        print("   -> Font not found. Expecting auto-download...")
    else:
        print("   -> Font already exists. Verifying load...")

    try:
        # distinct step: Instantiate renderer (triggers download)
        renderer = LLMRenderer()
        
        # Verify font file creation
        if os.path.exists(FONT_PATH) and os.path.getsize(FONT_PATH) > 0:
            print(f"   ✅ SUCCESS: Font located at {FONT_PATH}")
        else:
            print(f"   ❌ FAILURE: Font file is missing or empty.")
            return False

        # Verify UTF-8 capability flag
        if renderer.utf8_enabled:
            print("   ✅ SUCCESS: UTF-8 mode is ENABLED.")
        else:
            print("   ⚠️ WARNING: UTF-8 mode is DISABLED (Fallback active).")
        
        # Test render
        dummy_data = [("test_emoji.py", "print('🚀 Success')")]
        renderer.render(dummy_data, "test_llm_output.pdf")
        print("   ✅ SUCCESS: generated 'test_llm_output.pdf'")
        
        # Cleanup
        if os.path.exists("test_llm_output.pdf"):
            os.remove("test_llm_output.pdf")
            
        return True
    except Exception as e:
        print(f"   ❌ CRITICAL FAILURE in LLM Renderer: {e}")
        return False

def test_human_renderer():
    print("\n[2/2] Testing Human Renderer (Parallel Processing)...")
    
    # Create a fake heavy workload (100 'files') to force CPU spin-up
    dummy_data = []
    for i in range(50):
        dummy_data.append((f"file_{i}.py", "import os\ndef main():\n    print('Hello World')"))

    renderer = HumanRenderer(style='monokai')
    
    print(f"   -> Simulating render of {len(dummy_data)} files...")
    start_time = time.time()
    
    try:
        # This will trigger the ProcessPoolExecutor
        # If this hangs or crashes, the multiprocessing guard is missing
        renderer.render(dummy_data, "test_human_output.pdf")
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"   ✅ SUCCESS: Rendered in {duration:.2f} seconds.")
        print("   -> If this was near-instant, your parallel pool is working.")
        
        # Cleanup
        if os.path.exists("test_human_output.pdf"):
            os.remove("test_human_output.pdf")
        return True
    except Exception as e:
        print(f"   ❌ CRITICAL FAILURE in Human Renderer: {e}")
        print("   Hint: Did you protect the entry point with 'if __name__ == \"__main__\":'?")
        return False

if __name__ == "__main__":
    print("=== Vibecode Diagnostic Tool ===")
    
    llm_ok = test_llm_renderer()
    human_ok = test_human_renderer()
    
    print("\n" + "="*30)
    if llm_ok and human_ok:
        print("🎉 SYSTEM READY: All renderers are operational.")
        print("   You can now run 'python -m vibecode human' or 'python -m vibecode llm'")
    else:
        print("💥 SYSTEM FAILURE: Fix the errors above before running.")
    print("="*30)
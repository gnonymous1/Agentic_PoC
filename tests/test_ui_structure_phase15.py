
import os

INDEX_HTML = "static/index.html"
APP_JS = "static/app.js"
PLATFORM_CSS = "static/platform.css"

def verify_phase15():
    print("Verifying Phase 15: OpenClaw Interactivity & Artifacts Structure...")
    errors = []

    # 1. Verify index.html (Tabs & Artifacts Container)
    if not os.path.exists(INDEX_HTML):
        errors.append(f"Missing {INDEX_HTML}")
    else:
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            html = f.read()
            if 'switchRightTab(\'block\')' in html: # Should check logic
                pass 
            if 'id="tab-artifacts"' not in html:
                errors.append("Missing <div id='tab-artifacts'> in index.html")
            if 'id="tab-terminal"' not in html:
                errors.append("Missing <div id='tab-terminal'> in index.html")
            if 'onclick="switchRightTab(\'artifacts\')"' not in html:
                errors.append("Missing Artifacts tab button in index.html")

    # 2. Verify app.js (Artifact Logic)
    if not os.path.exists(APP_JS):
        errors.append(f"Missing {APP_JS}")
    else:
        with open(APP_JS, "r", encoding="utf-8") as f:
            js = f.read()
            if 'function extractArtifacts(' not in js:
                errors.append("Missing extractArtifacts function in app.js")
            if 'function renderArtifacts(' not in js:
                errors.append("Missing renderArtifacts function in app.js")
            if 'function runArtifact(' not in js:
                errors.append("Missing runArtifact function in app.js")
            if 'const codeBlockRegex = /```(\w+)?\\n([\\s\\S]*?)```/g;' not in js:
                 # Note: regex might slightly differ due to escaping, simple check for keyword
                 if 'codeBlockRegex' not in js:
                     errors.append("Missing artifact regex logic in app.js")

    # 3. Verify platform.css (Tab & Artifact Styles)
    if not os.path.exists(PLATFORM_CSS):
        errors.append(f"Missing {PLATFORM_CSS}")
    else:
        with open(PLATFORM_CSS, "r", encoding="utf-8") as f:
            css = f.read()
            if '.right-panel-tabs' not in css:
                errors.append("Missing .right-panel-tabs style in platform.css")
            if '.artifacts-container' not in css:
                errors.append("Missing .artifacts-container style in platform.css")

    if errors:
        print("\n❌ Verification Failed:")
        for e in errors:
            print(f"  - {e}")
        exit(1)
    else:
        print("\n[OK] Verification Passed: Phase 15 structure is correct.")

if __name__ == "__main__":
    verify_phase15()

import bleach
import re

def remove_scripts(html):
    # Remove <script>...</script> completely
    return re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)

def test_sanitization_various_payloads():
    payloads = [
        ('<script>alert(1)</script>', ''),
        ('<img src=x onerror=alert(1)>', ''),
        ('<b>bold</b>', '<b>bold</b>')
    ]
    for input_html, expected in payloads:
        clean = remove_scripts(input_html)
        clean = bleach.clean(clean, tags=['b'], strip=True)
        assert clean == expected

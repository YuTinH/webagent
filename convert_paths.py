import os
import re
import shutil

ROOT_DIR = 'sites'
KNOWN_PREFIXES = [
    'api/', 'static/', 'shop.local/', 'bank.local/', 'gov.local/',
    'pay.local/', 'card.local/', 'energy.local/', 'trip.local/', 'permit.local/'
]

def get_rel_root_prefix(file_path):
    path_from_root_dir = os.path.relpath(os.path.dirname(file_path), ROOT_DIR)
    if path_from_root_dir == '.':
        return './'
    depth = path_from_root_dir.count(os.sep) + 1
    return '../' * depth

def process_js_strings(content, rel_root):
    # 1. window.location.href = ...
    content = re.sub(
        r'''(window\.location\.href\s*=\s*)(["`])/(.+?)(["`])''', 
        r'''\1\2''' + rel_root + r'''\3\4''',
        content, flags=re.IGNORECASE
    )

    # 2. fetch(...)
    content = re.sub(
        r'''(fetch\s*\( [ \t]*)(["`])/(.+?)(["`])''', 
        r'''\1\2''' + rel_root + r'''\3\4''',
        content, flags=re.IGNORECASE
    )
    
    # 3. Variable assignments: let url = "/path"
    content = re.sub(
        r'''((?:let|const|var)\s+\w+\s*=\s*(["`]))/(.+?)\2''', 
        r'''\1''' + rel_root + r'''\3\2''', 
        content, flags=re.IGNORECASE
    )

    return content

def process_file(file_path):
    print(f"Processing {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    file_extension = os.path.splitext(file_path)[1].lower()
    
    rel_root = get_rel_root_prefix(file_path)

    if file_extension == '.html':
        # Phase 1: Inject window.RelRoot
        injection_script = f'<script>window.RelRoot = "{rel_root}";</script>'
        if '<head>' in content and injection_script not in content:
            content = content.replace('<head>', f'<head>\n{injection_script}', 1)
        elif '<head>' not in content and injection_script not in content: 
             content = injection_script + '\n' + content + '\n'

        # Phase 2: Replace absolute paths in HTML attributes
        content = re.sub(r'''(href|src|action)='(?!#)/([^']*)' ''', r'''\1='{}'\2'''.format(rel_root), content, flags=re.IGNORECASE)
        content = re.sub(r'''(href|src|action)='(?!#)/([^']*)' ''', r'''\1='{}'\2'''.format(rel_root), content, flags=re.IGNORECASE)

        # Phase 3: Replace absolute paths in JS string literals ONLY within <script> blocks
        def replace_js_in_script_tag(match):
            js_content = match.group(1)
            return f'<script>{{process_js_strings(js_content, rel_root)}}</script>'
        
        content = re.sub(r'<script>(.*?)</script>', replace_js_in_script_tag, content, flags=re.DOTALL | re.IGNORECASE)

        # Phase 4: Replace absolute paths in inline event handlers
        def replace_js_in_event_handler(match):
            event_attr = match.group(1)
            quote = match.group(2)
            js_content = match.group(3)
            return f'{{event_attr}}={{quote}}{{process_js_strings(js_content, rel_root)}}{{quote}}'

        content = re.sub(r"(on[a-z]+)=([\'"])(.*?)\2", replace_js_in_event_handler, content, flags=re.IGNORECASE)

    elif file_extension == '.js':
        content = process_js_strings(content, rel_root)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Modified: {file_path}")
    else:
        print(f"  No changes: {file_path}")

def main():
    for root, _, files in os.walk(ROOT_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path == os.path.join(os.getcwd(), 'convert_paths.py'):
                continue
            if file_path.endswith(('.html', '.js')):
                process_file(file_path)

if __name__ == '__main__':
    main()

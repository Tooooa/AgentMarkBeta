import os
import re
import argparse

def main():
    parser = argparse.ArgumentParser(description="Identify markdown dead links, orphan files, orphan assets, and empty directories.")
    parser.add_argument("target_dir", nargs="?", default=".", help="Root directory to scan (default: current directory)")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.target_dir)

    md_files = []
    image_files = []
    all_files = set()
    empty_dirs = []

    for root, dirs, files in os.walk(base_dir):
        # Skip hidden directories, node_modules, third_party to reduce noise
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'third_party']]
        
        if len(dirs) == 0 and len(files) == 0:
            empty_dirs.append(root)
            
        for file in files:
            if file.startswith('.'):
                continue
            full_path = os.path.join(root, file)
            all_files.add(full_path)
            if file.lower().endswith('.md'):
                md_files.append(full_path)
            elif file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
                image_files.append(full_path)

    referenced_files = set()
    dead_links = []

    link_pattern = re.compile(r'\]\((.*?)\)')

    for md in md_files:
        try:
            with open(md, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue
        
        links = link_pattern.findall(content)
        for link in links:
            # Ignore external, email, block anchors
            if link.startswith(('http', 'mailto:', '#', 'attachment:', 'file:')):
                continue
                
            # Remove hash suffixes
            target_path = link.split('#')[0]
            if not target_path:
                continue
                
            full_target = os.path.normpath(os.path.join(os.path.dirname(md), target_path))
            referenced_files.add(full_target)
            
            if not os.path.exists(full_target):
                dead_links.append({"source": md, "target": target_path})

    orphan_mds = []
    for md in md_files:
        filename = os.path.basename(md)
        # Core index files shouldn't be counted as orphans, they are the root nodes.
        if filename.lower() in ['index_map.md', 'agents.md', 'architecture.md', 'readme.md', 'index.md']:
            continue
        if md not in referenced_files:
            orphan_mds.append(md)

    orphan_assets = []
    for img in image_files:
        if img not in referenced_files:
            orphan_assets.append(img)

    print("=== 1. Dead Links ===")
    for d in dead_links:
        print(f"Source: {d['source'].replace(base_dir, '')} -> [DEAD] {d['target']}")

    print("\n=== 2. Orphan MD Files ===")
    for o in orphan_mds:
        print(f"Orphan: {o.replace(base_dir, '')}")

    print("\n=== 3. Orphan Assets ===")
    for o in orphan_assets:
        print(f"Orphan asset: {o.replace(base_dir, '')}")

    print("\n=== 4. Empty Dirs ===")
    for d in empty_dirs:
        print(f"Empty dir: {d.replace(base_dir, '')}")

if __name__ == "__main__":
    main()

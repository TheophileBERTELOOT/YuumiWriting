# AuthorTool — éditeur de roman modulaire

Prototype Python/PySide6 d'un éditeur de texte pour roman avec :

- barre d'outils en haut ;
- arborescence de fichiers à gauche ;
- éditeur central ;
- indicateurs d'écriture à droite ;
- architecture modulaire pour ajouter des analyseurs de style.

## Installation

```bash
cd author_tool
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows
pip install -r requirements.txt
python main.py
```

## Structure

```text
author_tool/
├── main.py
├── requirements.txt
├── app/
│   ├── core/
│   │   ├── document_manager.py
│   │   └── settings.py
│   ├── analysis/
│   │   ├── analyzer_base.py
│   │   ├── basic_stats.py
│   │   └── registry.py
│   ├── ui/
│   │   ├── editor.py
│   │   ├── file_tree.py
│   │   ├── indicators_panel.py
│   │   └── main_window.py
│   └── utils/
│       └── text.py
```

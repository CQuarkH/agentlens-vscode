# AgentLens VSCode Extension — Cómo Usar

## Requisitos

- Python 3.10+
- Node.js 18+
- Visual Studio Code

## Inicio Rápido

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/SwareUG/context-debt-cicd.git
   cd context-debt-cicd
   ```

2. **Crear y activar un entorno virtual de Python**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Abrir la carpeta de la extensión en VSCode**
   ```bash
   code agentlens-vscode
   ```

4. **Iniciar el Extension Development Host**
   - Presionar `F5` en VSCode
   - Se abre una nueva ventana con la extensión cargada

5. **Abrir un archivo markdown de ejemplo**
   - En la nueva ventana, abrir `samples/cartography-cncf_cartography.md`

6. **Ejecutar el comando de la extensión**
   - Presionar `Ctrl+Shift+P`
   - Escribir y seleccionar **"AgentLens: Show AST Visualization"**
   - El panel webview se abre en el costado

7. **Usar la extensión**
   - Hacer clic en **"Load Static Tree"** para ver la jerarquía del AST
   - Hacer clic en **"Load Evolution Timeline"** para ver el historial de cambios entre commits
   - Hacer clic en cualquier nodo **rule** para resaltar su instrucción en el editor markdown

## Caché

Los ASTs precomputados están incluidos en `cache/` para que todo funcione de inmediato sin necesidad de tokens de API. También puedes usar tus propios archivos markdown — la extensión generará ASTs vía LLM si no están en caché.

## Estructura del Proyecto

```
agentlens-vscode/
├── backend/           # Backend Python FastAPI
│   ├── main.py
│   ├── ast_service.py
│   ├── cache_manager.py
│   ├── domain_models.py
│   ├── llm_service.py
│   └── requirements.txt
├── src/               # Código fuente TypeScript de la extensión
│   ├── extension.ts
│   ├── backendManager.ts
│   ├── webview.ts
│   └── apiClient.ts
├── media/             # Frontend del webview
│   ├── staticView.js
│   ├── evolutionView.js
│   └── styles.css
├── cache/             # Caché de ASTs precomputados
├── samples/           # Archivos markdown de ejemplo
├── package.json
└── HOW_TO_USE.md
```

# AgentLens VSCode Extension — Cómo Usar

## Evaluación rápida via GitHub Codespaces (recomendado)

1. **Abrir el Codespace**
   - Ve a [https://github.com/CQuarkH/agentlens-vscode](https://github.com/CQuarkH/agentlens-vscode)
   - Click **Code** → **Open with Codespaces** → **Create codespace on main**
   - O usa el link directo: [https://codespaces.new/CQuarkH/agentlens-vscode](https://codespaces.new/CQuarkH/agentlens-vscode)

2. **Esperar la configuración automática** (~2-3 min)
   - El contenedor instala Python, npm, compila y empaqueta la extensión automáticamente
   - Al terminar se abre el archivo `cartography-cncf_cartography.md`

3. **Abrir la visualización**
   - `Ctrl+Shift+P` → escribe `AgentLens: Show AST Visualization` → Enter
   - Espera ~5 segundos a que arranque el backend
   - Aparece la visualización AST en una pestaña nueva

4. **Interacción**
   - **Vista Estática**: Dentro del panel de la extensión, hacer click en el botón **"Load Static Tree"** para cargar el árbol colapsable con métricas (LBL, RUL, COD, FRE, LEN, SYM).
   - **Vista Evolutiva**: Dentro del panel de la extensión, hacer click en el tab **"Evolution Timeline"**, y luego en el botón **"Load Evolution Tree"** para cargar el timeline de cambios del archivo entre commits. Esto permite ir viendo como van creciendo o decreciendo las métricas en cada cambio de version del archivo.
   - **Colapsar paneles**: Click en el badge **"Metrics"** o **"Added vs Deleted"** para ocultar/mostrar
   - **Seleccionar regla**: Click en cualquier nodo → se marca con borde azul

5. **Probar otros samples**
   - Una vez evaluado `cartography-cncf_cartography.md`, abre cualquiera de estos desde el explorador de archivos:
     - `samples/selfxyz_self.md`
     - `samples/antimetal_system-agent.md`
   - Vuelve a ejecutar `AgentLens: Show AST Visualization`

## Notas

- Todo funciona sin internet una vez abierto el Codespace (los ASTs están precargados en `cache/`)


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
└── README.md
```

# AgentLens VSCode Extension

Visualización interactiva de Árboles AST (Abstract Syntax Tree) de instrucciones para agentes de IA, extraídas desde archivos `AGENTS.md` o `CLAUDE.md`. La extensión se conecta a un backend local en Python que reutiliza toda la lógica de extracción, migración de esquemas y visualización del pipeline [context-debt-cicd](https://github.com/anomalyco/context-debt-cicd).

---

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                   VSCode Extension                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ extension.ts│  │ backendMgr.ts│  │ apiClient.ts│ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬─────┘ │
│         │                │                  │        │
│  ┌──────┴────────────────┴──────────────────┴─────┐ │
│  │              webview.ts (Webview Panel)        │ │
│  │  ┌─────────────────┐  ┌──────────────────────┐ │ │
│  │  │ staticView.js   │  │ evolutionView.js     │ │ │
│  │  │ (D3.js árbol)   │  │ (D3.js diff+línea t)│ │ │
│  │  └─────────────────┘  └──────────────────────┘ │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (127.0.0.1:8765)
┌──────────────────────┴──────────────────────────────┐
│              FastAPI Backend (Python)                │
│  ┌────────────┐  ┌───────────┐  ┌────────────────┐ │
│  │ main.py    │  │ast_service│  │ llm_service    │ │
│  │ (/api/*)   │  │.py        │  │ .py            │ │
│  └──────┬─────┘  └───────────┘  └────────────────┘ │
│         │                                           │
│  ┌──────┴─────────────────────────────────────────┐ │
│  │ cache_manager.py (~/.agentlens/{repo}/...)     │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Componentes

1. **Backend Python (FastAPI)** — Servidor HTTP local que ejecuta toda la lógica del pipeline: extracción LLM, migración de esquemas, construcción de árboles D3.js y cálculo de diffs entre commits. Se comunica con la extensión en `127.0.0.1:8765`.

2. **Extensión VSCode (TypeScript)** — Cliente que gestiona el ciclo de vida del backend (lo inicia como proceso hijo, monitorea salud, lo detiene al desactivar la extensión), administra el panel Webview y maneja los diálogos de confirmación para generación vía LLM.

3. **Webview D3.js** — Interfaz de usuario con dos pestañas:
   - **Static Tree**: Árbol jerárquico colapsable que muestra la taxonomía completa `Root → Category → Label → Rule` con métricas visuales (FRE, código, símbolos).
   - **Evolution Timeline**: Línea de tiempo con slider animado que recorre commits históricos, mostrando nodos agregados/eliminados con diff visual, más un panel "Added vs Deleted" con barras por commit.

### Flujo de Datos

```
Archivo .md abierto
        │
        ▼
Webview solicita AST → POST /api/tree
        │
        ├── ✅ En caché → Devuelve JSON del árbol → D3.js renderiza
        │
        └── ❌ No en caché → Muestra diálogo:
                "El AST no está en caché. ¿Generar usando LLM?"
                    │
                    ├── "Sí" → POST /api/generate → LLM extrae → migra
                    │          → guarda en ~/.agentlens/ → renderiza
                    │
                    └── "Cancelar" → No hace nada
```

Para evolución, el flujo es similar pero chequea múltiples commits: si faltan ASTs intermedios, se ofrecen generarlos todos.

---

## Requisitos

### Sistema
- Python 3.10+
- Node.js 18+ y npm
- Visual Studio Code 1.84+

### Python
Las dependencias del backend se listan en `backend/requirements.txt`:
```
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.0.0
anthropic>=0.30.0
python-dotenv>=1.0.0
textstat>=0.7.0
```

### Node.js
Las dependencias de desarrollo se instalan con npm:
```bash
npm install
```

---

## Instalación y Despliegue Local

### 1. Clonar / Situarse en el directorio

```bash
cd agentlens-vscode
```

### 2. Preparar el entorno Python

Se recomienda usar un entorno virtual. El backend puede residir dentro del proyecto `context-debt-cicd` o funcionar de forma independiente; lo único que necesita es poder importar `src/domain/models.py` del proyecto base.

```bash
# Opción A: Usar el venv del proyecto padre (si agentlens-vscode/ está dentro de context-debt-cicd)
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Opción B: Instalar globalmente
pip install -r backend/requirements.txt
```

### 3. Compilar la extensión TypeScript

```bash
npm install
npm run compile
```

Esto genera los archivos `.js` en `out/`.

### 4. Configurar VSCode

Abre la carpeta `agentlens-vscode/` en VSCode y presiona `F5` para iniciar una ventana de **Extension Development Host**.

**Configuraciones disponibles** (`agentlens.pythonPath`, `agentlens.backendPort`, `agentlens.projectRoot`):

| Propiedad | Default | Descripción |
|---|---|---|
| `agentlens.pythonPath` | `python3` | Ruta al intérprete Python que ejecutará el backend |
| `agentlens.backendPort` | `8765` | Puerto para el servidor local |
| `agentlens.projectRoot` | `""` | Ruta al proyecto `context-debt-cicd` (para resolver `src/domain/models.py`). Si está vacío, se usa el workspace root. |

### 5. Uso

1. Abre un archivo `.md` (p.ej. `AGENTS.md` o `CLAUDE.md`).
2. Ejecuta el comando `AgentLens: Show AST Visualization` desde la paleta de comandos (`Ctrl+Shift+P`).
3. La extensión inicia el backend automáticamente.
4. Haz clic en **"Load Static Tree"** o **"Load Evolution Timeline"**.
5. Si el AST no está en caché, se te preguntará si deseas generarlo (requiere `ANTHROPIC_API_KEY`).

---

## Estructura de Caché y Datos Existentes

### Sistema de Caché Local

Todos los ASTs generados se almacenan en `~/.agentlens/{repo_name}/` con la siguiente estructura:

```
~/.agentlens/{repo_name}/
├── trees/
│   └── {archivo}.json              → AST migrado (V2) para el archivo
└── evolution/
    ├── file_history.json           → Historial de commits del archivo
    └── trees/
        └── {sha}.json              → AST por commit (para evolución)
```

### Reutilizar ASTs ya extraídos del proyecto base

Si ya ejecutaste el pipeline `pipeline.sh` del proyecto `context-debt-cicd`, los ASTs extraídos están en:

| Pipeline | Ruta original | Lo contiene |
|---|---|---|
| Estático (V2 migrado) | `dataset/json_trees/llm_forced_output/` | Archivos `{nombre}.json` con esquema V2 (Root → Category → Label → Rule) |
| Evolución | `dataset/evolution_exp/json_trees/migrated_jsons/{repo}/` | Archivos `{sha}.json` por commit |

Para evitar re-extraer con LLM, copia esos JSONs a la caché local:

```bash
# AST estático
cp dataset/json_trees/llm_forced_output/mi_archivo.json \
   ~/.agentlens/mi_repo/trees/mi_archivo.json

# ASTs de evolución
cp dataset/evolution_exp/json_trees/migrated_jsons/mi_repo/*.json \
   ~/.agentlens/mi_repo/evolution/trees/

# Historial de commits
cp dataset/evolution_exp/file_history.json \
   ~/.agentlens/mi_repo/evolution/file_history.json
```

> **Nota**: El backend también sirve como puente para regenerar estos datos. Si los ASTs ya existen en el proyecto base pero no en la caché local, la forma más práctica es:
> 1. Escribir un script corto que lea `dataset/json_trees/llm_forced_output/` y copie cada archivo a `~/.agentlens/{repo}/trees/`.
> 2. O simplemente dejar que la extensión los genere bajo demanda (consume créditos de API).

---

## Preparación para Despliegue Externo (VSCode Marketplace)

Para empaquetar y publicar la extensión en el VSCode Marketplace:

### 1. Empaquetar con vsce

```bash
# Instalar la herramienta de empaquetado
npm install -g @vscode/vsce

# Generar el .vsix
vsce package

# Esto produce agentlens-vscode-0.1.0.vsix
```

### 2. Publicar en Marketplace

```bash
vsce publish
```

Requiere haber creado un publisher en `https://marketplace.visualstudio.com/manage` y tener un token de acceso personal de Azure DevOps.

### 3. Instalación offline

```bash
code --install-extension agentlens-vscode-0.1.0.vsix
```

### 4. Consideraciones para despliegue externo

- **Backend empaquetado**: El backend Python no se incluye en el `.vsix`. El usuario debe tener Python y las dependencias instaladas. En una versión futura se podría empaquetar con PyInstaller o distribuir vía pip.
- **Modelos compartidos**: La extensión necesita encontrar `src/domain/models.py`. Para despliegue externo, hay dos opciones:
  - **Opción A (recomendada para ahora)**: El usuario clona el proyecto `context-debt-cicd` y configura `agentlens.projectRoot` apuntando a él.
  - **Opción B**: Copiar `src/domain/models.py` dentro de `backend/` de la extensión y ajustar el import a local.
- **LLM API Key**: Se requiere `ANTHROPIC_API_KEY` en el entorno para generación. Para la visualización de ASTs ya cacheados, no es necesaria.

---

## API del Backend

| Endpoint | Método | Payload | Respuesta |
|---|---|---|---|
| `/health` | GET | — | `{"status": "ok"}` |
| `/api/tree` | POST | `{"file_path": "...", "repo": "...", "commit": "..."}` | `{"status": "cached", "data": {...}}` o `404` |
| `/api/evolution` | POST | `{"file_path": "...", "repo": "..."}` | `{"status": "complete", "data": {...}}` o `{"status": "incomplete", "missing_commits": [...]}` |
| `/api/generate` | POST | `{"file_path": "...", "repo": "..."}` | `{"status": "generated", "data": {...}}` |

---

## Variables de Entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `ANTHROPIC_API_KEY` | Solo para generación | API key de Anthropic para extraer ASTs vía Claude |
| `AGENTLENS_PORT` | No (default: 8765) | Puerto para el servidor FastAPI |

---

## Estructura del Repositorio

```
agentlens-vscode/
├── backend/
│   ├── main.py            # Servidor FastAPI (punto de entrada)
│   ├── ast_service.py     # Construcción de árboles y lógica de diff
│   ├── cache_manager.py   # Lectura/escritura de ~/.agentlens/
│   ├── llm_service.py     # Extracción vía Anthropic + migración de esquema
│   └── requirements.txt   # Dependencias Python
├── src/
│   ├── extension.ts       # Activación de la extensión, comando showAST
│   ├── backendManager.ts  # Spawn y ciclo de vida del proceso Python
│   ├── apiClient.ts       # Cliente HTTP para la API local
│   └── webview.ts         # Panel Webview con pestañas y flujo de caché
├── media/
│   ├── staticView.js      # Visualización D3.js del árbol estático
│   ├── evolutionView.js   # Visualización D3.js de evolución (sin "Cumulative Changes")
│   └── styles.css         # Estilos compartidos del Webview
├── package.json           # Manifiesto de la extensión VSCode
└── tsconfig.json          # Configuración de TypeScript
```

---

## Licencia

MIT

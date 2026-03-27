# Pipeline Data Enrichment

Este documento describe la fase de Ingesta y Enriquecimiento de Datos del pipeline.

## Fase 1: Enriquecimiento de Agentes (`scripts/1_enrich_agents.py`)

Este paso se encarga de procesar los datos en crudo (`raw_dataset.csv`) que contienen definiciones estructuradas de repositorios y acoplarles su respectivo documento de agente descargado (almacenado en la caché).

### Proceso:
1. **Lectura de Entrada**: El script lee el archivo `dataset/raw_dataset.csv`.
2. **Generación de Metadatos**: Extrae el nombre del repositorio (`owner/repo`) y sus etiquetas (categorías) asociadas de las columnas correspondientes a las Labels.
3. **Validación de Caché**: Para cada repositorio, busca si existe el archivo markdown correspondiente (`owner_repo.md`) dentro del directorio de caché (`dataset/agents_cache/`). Si el archivo no está cacheado localmente, el script **ignora** la fila en cuestión, imprime un aviso ("Skipping...") y continúa, evitando intentos de descarga externos.
4. **Enriquecimiento**: Si el archivo caché está presente, se lee su contenido y se inyecta un bloque de metadatos (YAML Frontmatter) en la cabecera. Este bloque incluye el identificador completo del repositorio y el listado de categorías extraídas del CSV original.
5. **Generación de Salida**: Escribe el nuevo documento en la carpeta `dataset/enriched_agents/`, conservando el nombre original del archivo cacheado pero ahora enriquecido y estructurado para las próximas fases.

### Inputs:
- `dataset/raw_dataset.csv` (o `raw-dataset.csv`): Archivo CSV base con el listado tabular de repositorios y sus categorías.
- `dataset/agents_cache/`: Directorio temporal/repositorio local con todos los archivos markdown crudos para cada agente (`owner_repo.md`).

### Outputs:
- `dataset/enriched_agents/`: Directorio final que contiene los archivos `.md` resultantes, con el YAML Frontmatter implementado inyectado al tope de cada documento.

### Ejemplo de Salida:
```markdown
---
repo: "0x-j/aptos-full-stack-template"
categories: ["System Overview", "Architecture", "Development Process", "Test", "Configuration & Environment", "Maintanability"]
---
content...
```

## Fase 2: Extracción Estructurada

Para propósitos de evaluación académica comparando la eficiencia y fiabilidad de métodos LLM vs métodos determinísticos tradicionales, esta fase cuenta con **tres variantes**. Todas ellas procesan los archivos resultantes de la Fase 1 y generan un objeto JSON que representa un AST (Abstract Syntax Tree) normalizado del contexto del documento, categorizando las reglas extraídas.

### Estructura del JSON Esperado (Output)
Independientemente de la variante utilizada, el esquema de salida unificado es el siguiente:

```json
{
  "projectInfo": {
    "repoName": "<nombre_repo>",
    "agentsMdSource": "<archivo_origen.md>"
  },
  "rootNode": {
    "id": "root",
    "label": "AGENTS.md Context",
    "type": "root",
    "children": [
      {
        "id": "macro_<nombre_categoria>",
        "label": "<Nombre Categoría Macro (ej. General)>",
        "type": "category",
        "count": <total_reglas_en_macro_categoria>,
        "children": [
          {
            "id": "cat_<nombre_label>",
            "label": "<Nombre Label / Sub-Categoría>",
            "type": "label",
            "count": <total_reglas_en_label>,
            "children": [
              {
                "id": "rule_<num_secuencial>",
                "type": "rule",
                "content": {
                  "text": "<Instrucción completa identificada en el markdown>",
                  "originalHeader": "<Título de la sección H2/H3 a la que pertenece>"
                },
                "metadata": {
                  "format": "<ListItem|Paragraph>"
                }
              }
            ]
          }
        ]
      }
    ]
  }
}
```

### Variante A: LLM Local (`scripts/2a_extract_json_llm.py`)
Utiliza un modelo Local Small Language Model (SLM) iterando con un servidor compatible (ej. LMStudio con Qwen 3.5).
- **Proceso**: El script extrae el bloque de metadatos del archivo y le pasa el texto en crudo al modelo junto con el diccionario maestro de categorías. Luego parsea la salida en crudo garantizando la estructura dictada de JSON.
- **Input**: Archivos `.md` de `dataset/enriched_agents/`.
- **Output**: Árboles JSON guardados en `dataset/json_trees/llm/`.

### Sub-Variante 2A: SLM vía OpenRouter (`scripts/2a_openrouter_extract_json.py`)
Utiliza un SLM de última generación (ej. `qwen/qwen-3.5-9b`) remotamente pasando a través de la API ruteada de OpenRouter, pero preservando la compatibilidad de "Structured Output" del cliente de OpenAI.
- **Proceso**: Idéntico a la variante 2A local, pero forzando garantizadamente la salida estructurada a nivel de API. Se inyecta la constante `JSON_SCHEMA` (esquema JSON duro con `strict: True` y `additionalProperties: False`) en el parámetro `response_format` del cliente de OpenAI, lo que obliga al modelo a generar una compatibilidad sintáctica perfecta del AST sin alucinaciones.
- **Dependencias y Auth**: Requiere `pip install openai` y configurar la variable de entorno `OPENROUTER_API_KEY`.
- **Input**: Archivos `.md` de `dataset/enriched_agents/`.
- **Output**: Árboles JSON guardados en una nueva sub-carpeta `dataset/json_trees/llm_forced_output/`.

### Variante B: AST Parser Determinista (`scripts/2b_extract_json_parser.py`)
No utiliza IA; emplea heurísticas determinísticas y la estructura generada por **Pandoc**.
- **Proceso**: 
  - Ejecuta la CLI de `pandoc` subyacentemente para transformar de Markdown a JSON AST nativo de Pandoc.
  - Recorre el JSON de manera recursiva asegurando extraer texto de nodos anidados (como `Quoted`, `Table`, `Header`, `Para`, `BulletList`).
  - Asigna la categoría macheando palabras clave contra el diccionario de categorías general o el array inyectado previamente.
- **Input**: Archivos `.md` de `dataset/enriched_agents/`.
- **Output**: Árboles JSON guardados en `dataset/json_trees/parser/`.

### Variante C: LLM Comercial vía API (`scripts/2c_extract_json_llm_api.py`)
Utiliza un modelo comercial de alto rendimiento de Anthropic (Claude 4.5 Sonnet) a través de su API oficial.
- **Proceso**: Similar a la Variante A, extrae contexto y pide la estructuración JSON AST exacta. Destaca por su alta fiabilidad y capacidad intelectual. Requiere una clave de API válida.
- **Input**: Archivos `.md` de `dataset/enriched_agents/`.
- **Output**: Árboles JSON guardados en `dataset/json_trees/llm_api/`.

## Fase 2.5: Validación de Resultados
Para validar cuantitativamente la calidad y la veracidad de los JSON generados por las variantes de la Fase 2 (y mitigar amenazas a la validez), se ejecutan rutinas de *testing* automáticas.

### Dependencias
Para correr los scripts de validación, necesitas instalar el validador oficial de esquemas JSON de Python:
```bash
pip install jsonschema
```

### Script 2D: Validación Estructural (Completeness & Sintaxis)
`src/scripts/2d_validate_json_schema.py`

- **¿Qué evalúa?**: Verifica matemáticamente que los JSON generados cumplan al 100% con la estructura del AST requerida. Asegura que no falten campos obligatorios (`projectInfo`, `rootNode`), que los tipos de datos sean exactos (ej. `count` debe ser Integer), y que el LLM no haya inyectado propiedades fantasma.
- **Métrica obtenida**: *Schema Compliance Rate* (Integridad del Formato). Las variaciones que pasan esta prueba están garantizadas para consumirse por una UI/Visualización downstream sin romper el código.
- **Ejecución**:
```bash
python src/scripts/2d_validate_json_schema.py
```

### Script 2E: Validación Semántica (Ground-Truth Hallucinations)
`src/scripts/2e_validate_categories.py`

- **¿Qué evalúa?**: Funciona como un test de alucinación semántica. Lee el array de categorías base original (Ground Truth) inyectado al inicio del `.md` en la **Fase 1** y lo compara contra los nodos `category` generados en el árbol AST de la **Fase 2**. 
- **Métrica obtenida**: *Hallucination Rate*. Detecta y lista si el LLM o el Parser "inventaron" nuevas categorías para encapsular reglas en lugar de ceñirse estrictamente al array asignado para ese repositorio.
- **Ejecución**:
```bash
python src/scripts/2e_validate_categories.py
```

## Fase 3: UI Visualization (Avance V1)

El objetivo de esta fase es reducir drásticamente la carga cognitiva de leer archivos `AGENTS.md` kilométricos, transformando el JSON AST crudo en interfaces gráficas interactivas renderizadas en el navegador web.

Para garantizar la integridad estricta de los datos inyectados al frontend, la arquitectura pasó de usar diccionarios crudos de Python a un **Modelo de Dominio**.

### Arquitectura Orientada a Dominio (`src/domain/models.py`)
Antes de generar cualquier gráfica, el JSON extraído es validado e instanciado imperativamente mediante **Pydantic**. 
La clase `AgentASTDocument` actúa como el Aggregate Root. Todas las propiedades visuales (como `color`, `radio` del nodo, truncamiento de etiquetas y mapeo semántico `MUST`/`SHOULD`) están encapsuladas directamente dentro de las entidades (ej: `RuleCategory` y `AgentRule`). Esto elimina la lógica de presentación redundante (spaghetti) de los scripts de generación.



### Variante 1: Grafo de Fuerza Dirigida (`scripts/3_generate_visualization.py`)
Genera un archivo HTML interactivo con una **vista dividida (Split-View)**:
- **Izquierda**: Muestra el documento Markdown crudo original para lectura por referencias.
- **Derecha**: Renderiza un grafo de red usando `D3.js` (`d3.forceSimulation`). Los nodos (Reglas) orbitan dinámicamente alrededor de sus Categorías padre.
- **Interacción**: Permite hacer Zoom, Paneo (arrastrar el lienzo) y clic sobre los nodos para abrir un panel lateral con los metadatos profundos de la regla (Formato, Intensidad, Header Original).

**Ejecución:**
```bash
PYTHONPATH=. python src/scripts/3_generate_visualization.py dataset/json_trees/llm_forced_output/<archivo>.json
```

### Variante 2: Árbol Jerárquico Horizontal (`scripts/3b_generate_tree_visualization.py`)
Genera un diagrama estático utilizando `d3.tree()`. Elimina la física caótica de colisiones, permitiendo leer secuencialmente el árbol AST de izquierda a derecha.

#### Topología de Nodos
El árbol visual desglosa el contexto en cuaatro profundidades secuenciales:
1. **Nodos Raíz (Root):** Origen del árbol representando al repositorio (color gris oscuro).
2. **Macro-Categorías (Category):** Primer nivel de agrupamiento analítico. Existen 6 dominios inmutables con una semaforización de colores fijos que heredan visualmente hacia sus hijos:
   - **General:** Pizarra (`#94a3b8`)
   - **Implementation:** Azul (`#60a5fa`)
   - **Build:** Verde (`#4ade80`)
   - **Management:** Púrpura (`#c084fc`)
   - **Quality:** Rojo (`#f87171`)
   - **Uncategorized:** Gris Claro (`#e2e8f0`)
3. **Etiquetas (Label):** Áreas temáticas intermedias inferidas originalmente por el LLM en la Fase 2 (ej. *Tests*, *Architecture*, *Performance*) antes de ser categorizadas en el script de migración. Actúan como el segundo nivel de agrupamiento.
4. **Instrucciones (Rule):** Nodos terminales (hojas) que contienen el texto crudo y descriptivo de la acción extraída del Markdown.

**Ejecución:**
```bash
PYTHONPATH=. python src/scripts/3b_generate_tree_visualization.py dataset/json_trees/llm_forced_output/<archivo>.json
```

### Codificación Geométrica Dinámica de Categorías y Labels

Para los agrupadores (`Category` y `Label`), abandonamos los clásicos nodos redondos en favor de **nodos rectangulares responsivos**. Aprovechamos la geometría matemática del rectángulo para mapear volumétricamente el tamaño y la carga cognitiva acumulada de sus descendientes:

#### 1. Altura del Rectángulo (Height) = Volumen de Reglas Anidadas
- **Nodos Category:** Su altura matemática es la sumatoria de **todas las reglas** contenidas dentro de todos sus Labels hijos (`50px + rules*8`).
- **Nodos Label:** Su altura crece proporcionalmente en base a **la cantidad de reglas inmediatas** que alberga (`40px + rules*10`).
- **Interpretación:** De un solo vistazo vertical se aprecia geométricamente qué áreas del conocimiento concentran la mayor sumatoria de requerimientos técnicos.

#### 2. Anchura del Rectángulo (Width) = Diversidad Temática y Carga Cognitiva (FRE)
- **Nodos Category (Diversidad Temática):** Su anchura horizontal la determina **la cantidad de Labels internos** que alberga. Una Category muy ancha indica que el dominio abarca muchos temas/etiquetas diferentes (`140px + labels*25`).
- **Nodos Label (Carga Cognitiva):** Su anchura se determina evaluando su texto interno crudo con un motor NLP (`textstat`) para calcular la métrica de legibilidad **Flesch Reading Ease (FRE)**. 
- **Interpretación del Label:** Un Label **corto y contraído** alerta de instrucciones con altísima carga cognitiva (jerga, sentencias densas e ingeniería). Un Label horizontalmente **ancho**, indica instrucciones fluidas o párrafos introductorios fáciles de leer (`80px + FRE Score`).

#### 3. Grosor del Borde (Border Density) = Code Ratio
- **Lógica:** Se mide la proporción de instrucciones que contienen marcadores estructurales exclusivos de código (`{}`, `()`, `<>`, `.py`, `.js`, etc.) en relación con el total de instrucciones dentro de esa agrupación.
- **Interpretación:** Un borde **grueso y marcado** (hasta 8px) resalta inmediatamente que ese agrupamiento es puramente de ingeniería, código duro y comandos. Un borde excepcionalmente fino (1.5px) indica lineamientos organizacionales, procesos, o semántica teórica que carecen de fragmentos de código.

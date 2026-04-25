# Experimento: Analizar historia/evolucion de los archivos

Bien, ahora necesito aplicar un upgrade sobre el codigo. dicha nueva feature será la extracción de la historia y/o evolución de cada archivo AGENTS.md. Se propone seguir los siguientes pasos:

## Paso 1

Primero que todo, se debe analizar el conjunto de datos original enriquecido (dentro de dataset/enriched_agents/) mediante un script simple de python. El script debe analizar archivo por archivo, y tomar las categorías que aparecen como metadata del markdown, tomando sólo aquellos que tienen más categorías de 3 categorías, y exportandolos (copiándolos) a un nuevo directorio (dataset/enriched_agents_top_categories). Aquí un ejemplo de uno de esos archivos: 

``` ---
repo: "0x-j/aptos-full-stack-template"
categories: ["System Overview", "Architecture", "Development Process", "Test", "Configuration & Environment", "Maintanability"]
---
# Aptos Full Stack Template - AI Assistant Context 
```

## Paso 2

Luego, cuando ya se tengan los archivos con más de 3 categorías dentro de un nuevo directorio (dataset/enriched_agents_top_categories), se deben analizar cada uno de ellos individualmente. Esta tarea es netamente experimentación, por lo que su ejecución puede ser compleja. Se debe crear un script de python que analice cada archivo, y por cada uno debe tomar la cantidad de commits asociados a dicho archivo (commits donde ese archivo se haya modificado), la cantidad de releases asociados a dicho archivo (releases donde ese archivo se haya modificado), y con esa información anterior, se debe registrar la diferencia de lineas entre cada una de las versiones.

Finalmente, se debe plotear o registrar de alguna forma esta información obtenida anteriormente para cada archivo y entre todos los archivos también (utilizando conceptos estadísticos como tendencias, moda, etc). El objetivo final es aplicar una forma inteligente de filtrado de datos para quedarnos sólo con datos relevantes, así se puede tomar una decisión sobre qué archivos son interesantes/valiosos para poder generarles una historia completa sobre su evolución. La idea es obtener datos relevantes, para ajustarnos al presupuesto monetario.

Los resultados del experimento deben guardarse dentro de dataset/evolution_analysis/.

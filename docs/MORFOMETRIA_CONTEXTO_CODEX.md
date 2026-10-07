# Contexto técnico para corregir la medición morfométrica de peces

## 1. Propósito de este documento

Este documento es el contexto normativo para un agente de desarrollo tipo Codex.
Su objetivo es permitir la auditoría y corrección de un software que mide peces
en imágenes obtenidas en un medio acuático y que actualmente calcula las
medidas entre puntos mediante distancia euclidiana.

El software pertenece a una tesis sobre un sistema integrado de visión por
computadora para estimación morfométrica de peces con corrección óptica de la
interfaz agua–vidrio–aire.

El agente debe utilizar este documento como especificación técnica. No debe
inferir reglas geométricas únicamente a partir del código existente ni sustituir
las definiciones morfométricas por convenciones de una biblioteca.

## 2. Objetivo del sistema

El flujo general del proyecto es:

1. adquirir una imagen del pez dentro de una pecera;
2. calibrar la cámara y modelar la distorsión de lente;
3. corregir o modelar la refracción agua–vidrio–aire;
4. segmentar el pez y separar, cuando sea posible, cuerpo, cabeza y aletas;
5. localizar puntos o perfiles anatómicos;
6. transformar las coordenadas al espacio métrico correspondiente;
7. calcular las medidas morfométricas;
8. compararlas con una medida de referencia física;
9. informar el resultado y sus errores.

La longitud total es la medida primaria del proyecto. La profundidad corporal,
la longitud estándar y la longitud cefálica son medidas secundarias cuando están
incluidas en el alcance de la versión del software.

## 3. Principios obligatorios

- La definición anatómica precede a la fórmula geométrica.
- La transformación óptica y la medición morfométrica son etapas diferentes.
- Los puntos deben transformarse al mismo espacio en el que se define el eje.
- La distancia euclidiana no debe utilizarse automáticamente para toda medida.
- La selección de p1, p2, p3 y p4 es tan importante como la fórmula final.
- La misma convención debe utilizarse en código, interfaz, figuras, tablas,
  medición de referencia y resultados.
- Toda convención caudal, región corporal y tolerancia geométrica debe quedar
  documentada y configurable cuando sea necesario.
- Las medidas obtenidas con A, A', B y C solo son comparables si se documenta
  qué puntos y qué transformación utiliza cada método.

## 4. Puntos anatómicos

La nomenclatura canónica para esta especificación es:

- **p1:** extremo anterior del hocico. Debe definirse si corresponde a la punta
  del hocico, punta de la mandíbula o el punto más anterior visible.
- **p2:** extremo posterior asociado con la convención caudal elegida. Puede
  representar extremo de longitud total, centro de la horquilla, base de la
  aleta caudal u otra referencia explícita.
- **p3:** extremo dorsal de la sección corporal seleccionada.
- **p4:** extremo ventral de la misma sección corporal seleccionada.

No se debe mezclar esta nomenclatura con otra numeración histórica sin una tabla
de equivalencias. Si el repositorio ya usa nombres diferentes, conservar una
única nomenclatura interna y documentar los alias durante la migración.

## 5. Espacios de coordenadas

El sistema puede trabajar con varios espacios:

- **imagen original:** píxeles antes de corregir lente o refracción;
- **imagen sin distorsión:** coordenadas después de la corrección de lente;
- **imagen rectificada:** coordenadas de un plano transformado;
- **espacio métrico:** coordenadas expresadas en milímetros o centímetros;
- **espacio refractivo:** coordenadas obtenidas mediante el modelo de puerto
  plano y trazado de rayos.

Las coordenadas y el eje anatómico deben pertenecer al mismo espacio. El flujo
correcto es:

```text
puntos en imagen
  -> corrección/transformación óptica
  -> puntos métricos q1, q2, q3, q4
  -> estimación o selección del eje anatómico
  -> validación geométrica
  -> medición morfométrica
```

No es válido transformar los puntos a centímetros y continuar utilizando un eje
calculado en píxeles si la transformación no conserva exactamente esa relación.

## 6. Eje longitudinal anatómico

El eje longitudinal anatómico es la dirección cabeza–cola del pez en el plano o
espacio de medición. Se representa mediante un vector unitario:

```text
u = (ux, uy)
||u|| = 1
```

Si el pez está rectificado, horizontal y orientado con la cabeza a la izquierda
y la cola a la derecha:

```text
u = (1, 0)
n = (0, 1)
```

Si el pez forma un ángulo theta con el eje horizontal:

```text
u = (cos(theta), sin(theta))
n = (-sin(theta), cos(theta))
```

`n` es un vector perpendicular al eje longitudinal.

El eje puede mantenerse constante únicamente cuando el montaje exige y verifica
que todos los peces estén alineados. Si se permite rotación, debe estimarse por
imagen o debe rotarse la imagen a una orientación común.

No se debe estimar `u` directamente como la dirección p1–p2 si p2 puede estar
desplazado dorsoventralmente por la forma o la posición de la aleta caudal. Si
se hace eso, la proyección de p1–p2 será equivalente a la distancia euclidiana y
se perderá la distinción entre longitud longitudinal y diagonal.

## 7. Longitud p1–p2

La longitud p1–p2 es una medida longitudinal rectilínea. Si `q1` y `q2` son
los puntos en el espacio métrico y `u` es el eje anatómico unitario:

```text
L = abs(dot(q2 - q1, u))
```

La fórmula mide la separación entre las proyecciones de p1 y p2 sobre el eje
longitudinal. No mide necesariamente el segmento diagonal entre ambos puntos.

Ejemplo normativo:

```text
q2 - q1 = (4, 4)
u       = (1, 0)

L       = abs((4, 4) dot (1, 0)) = 4
distancia euclidiana = sqrt(4^2 + 4^2) = 5.656854...
```

La distancia euclidiana puede conservarse como valor auxiliar de diagnóstico,
pero no debe reemplazar a `L` cuando la medida requerida es longitudinal.

Cuando `u = (1, 0)`, puede utilizarse `abs(q2.x - q1.x)`, pero solo si:

- las coordenadas están en un espacio rectificado o métrico válido;
- el eje anatómico coincide con el eje x;
- la escala en los ejes está calibrada;
- la convención cabeza–cola está definida;
- la inclinación residual está dentro de la tolerancia.

La convención caudal de p2 debe ser explícita. El software no debe llamar
“longitud total” a cualquier extremo de la máscara sin documentar si la cola se
considera extendida, comprimida, llevada a la línea media o medida hasta una
horquilla.

## 8. Profundidad corporal p3–p4

La profundidad corporal es la mayor separación dorsoventral del cuerpo dentro de
la región anatómica definida por el protocolo. Debe medirse entre el perfil
dorsal y el perfil ventral en una misma sección transversal perpendicular al eje
longitudinal.

Para una sección válida:

```text
dot(q4 - q3, u) ~= 0
```

La tolerancia de `~=` debe ser configurable y expresarse preferentemente como
ángulo o error relativo respecto de la profundidad.

La profundidad máxima debe buscarse entre secciones:

```text
Dmax = max_s D(s)
```

donde `D(s)` es la separación entre el perfil dorsal y ventral en la sección
perpendicular ubicada en la posición longitudinal `s`.

La búsqueda debe excluir las aletas y aplicar la región corporal definida por el
protocolo. No se deben seleccionar de manera independiente el píxel más alto y
el más bajo de toda la máscara si pertenecen a estaciones longitudinales
diferentes.

Si p3 y p4 ya son extremos de una misma sección perpendicular, su distancia
euclidiana coincide con la profundidad. La condición principal es la correcta
selección de los puntos, no la sustitución mecánica de una fórmula por otra.

## 9. Diferencia entre una imagen alineada y una imagen arbitraria

Cuando el pez está horizontal y la imagen está rectificada:

```text
u = (1, 0)
n = (0, 1)
L = abs(x2 - x1)
D = abs(y4 - y3)       # solo para p3 y p4 de la misma sección
```

Cuando el pez está rotado, no se debe asumir que `x` representa longitud ni que
`y` representa profundidad. Debe utilizarse `u` y `n`, o debe alinearse la imagen
antes de medir.

Si se establece una tolerancia angular, el agente debe documentar su efecto. Por
ejemplo, usar un eje horizontal fijo para un segmento que forma un ángulo theta
produce una componente longitudinal proporcional a `cos(theta)`. La tolerancia
no debe inventarse como una norma universal: debe justificarse por el error
admisible, la resolución, la escala y el objetivo experimental.

## 10. Segmentación y perfiles

La máscara puede incluir fondo, cabeza, cuerpo y aletas. La extracción de puntos
debe declarar qué clases se utilizan para cada medida.

- p1 puede provenir de cabeza+cuerpo, según la definición del hocico.
- p2 puede requerir cuerpo+aleta si la convención incluye la cola.
- p3 y p4 deben provenir del cuerpo, excluyendo las aletas.
- Los fragmentos desconectados deben tratarse según una regla explícita.
- Las oclusiones, contornos espurios y extremos de baja confianza deben generar
  una advertencia o invalidar la medición.

La elección del extremo de una máscara no es automáticamente equivalente al punto
anatómico definido en el protocolo.

## 11. Métodos ópticos del proyecto

El proyecto compara cuatro condiciones o métodos:

- **A:** escala directa mediante marcador ArUco colocado en el vidrio.
- **A':** escala directa mediante marcador coplanar con el pez, utilizado como
  control cuando corresponda.
- **B:** cámara calibrada bajo agua, conversión de puntos mediante rayos y
  plano métrico conocido.
- **C:** cámara calibrada en aire y modelo explícito de puerto plano, con trazado
  aire–vidrio–agua mediante la ley de Snell.

Los métodos A y A' no proporcionan necesariamente la misma información de
profundidad que B y C. Por eso una diferencia entre métodos no debe atribuirse
automáticamente a la refracción.

Si se comparan métodos ópticos, debe documentarse si todos reciben los mismos
puntos anatómicos o si cada método vuelve a buscar extremos después de
transformar la imagen. Ambas decisiones son válidas para preguntas distintas,
pero no deben mezclarse.

## 12. Requisitos del software que debe corregirse

El agente debe localizar y revisar:

1. extracción de la máscara;
2. separación de cuerpo, cabeza y aletas;
3. selección de p1 y p2;
4. selección de p3 y p4;
5. estimación del eje longitudinal;
6. aplicación de calibración y refracción;
7. conversión de píxeles a milímetros o centímetros;
8. cálculo euclidiano actual;
9. exportación de resultados y metadatos;
10. pruebas existentes.

Debe distinguirse entre:

- distancia euclidiana auxiliar;
- proyección longitudinal;
- proyección dorsoventral;
- distancia de una sección corporal;
- longitud de una curva corporal;
- extensión máxima de una máscara.

No todas estas cantidades son intercambiables.

## 13. Validaciones obligatorias

El software debe incluir o permitir verificar como mínimo:

### Caso A: proyección diagonal

```text
p1 = (0, 0)
p2 = (4, 4)
u  = (1, 0)
resultado longitudinal esperado = 4
distancia euclidiana auxiliar    = 5.656854...
```

### Caso B: rotación conjunta

Rotar los puntos y el eje anatómico por el mismo ángulo. La medida proyectada
debe permanecer constante, salvo errores numéricos.

### Caso C: profundidad válida

```text
p3 = (20, -15)
p4 = (20, 25)
u  = (1, 0)
profundidad esperada = 40
```

### Caso D: profundidad inválida

Si p3 y p4 tienen posiciones longitudinales diferentes y no cumplen la tolerancia
de perpendicularidad, la medición debe marcarse como inválida o corregirse
mediante una intersección con la misma sección.

### Caso E: aletas

Una aleta dorsal o ventral no debe aumentar la profundidad corporal si el
protocolo define la medida sobre el cuerpo.

### Caso F: escalas diferentes

Si la transformación tiene distinta escala en x e y, no se deben utilizar
directamente diferencias de píxeles. Primero deben obtenerse coordenadas métricas.

## 14. Resultados y metadatos

Cada resultado debe conservar, cuando sea posible:

- p1, p2, p3 y p4 originales;
- puntos transformados;
- unidad de medida;
- método óptico utilizado;
- eje `u` y normal `n` utilizados;
- ángulo estimado del pez;
- convención caudal;
- región corporal de búsqueda;
- si se excluyeron aletas;
- distancia euclidiana auxiliar;
- longitud proyectada;
- profundidad obtenida;
- advertencias y motivos de invalidez;
- versión del algoritmo y configuración.

## 15. Referencias de contexto del proyecto

Los siguientes archivos contienen el marco académico y la guía experimental.
Deben utilizarse para consultar fundamentos, alcance y método, pero el agente
debe tomar las reglas operacionales de este documento como la especificación
ejecutable:

- `Tesis Ezequiel 2026 - Ideas .txt`
- `cap2.md`
- `seccionMarcoTeorico.tex`
- `Marco-Teórico-actualizado-13-08-26.txt`
- `GUIA_MAESTRA_tesis_ezequiel_3.pdf`
- `Segmentación de imágenes con redes neuronales para medición morfológica de peces.pdf`

## 16. Regla para tareas posteriores

Cada tarea que se solicite al agente debe indicar:

1. qué sección de este documento aplica;
2. qué archivos del repositorio debe inspeccionar;
3. qué comportamiento actual debe comprobar;
4. qué resultado esperado debe implementar;
5. qué pruebas debe ejecutar;
6. qué supuestos o decisiones debe reportar.

El agente no debe corregir silenciosamente ambigüedades anatómicas. Si una
decisión depende de la especie, el protocolo de longitud o la configuración
experimental, debe señalarla y hacerla explícita en configuración o documentación.

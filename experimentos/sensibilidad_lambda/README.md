# Sensibilidad de los pesos de la función objetivo

Este directorio contiene el análisis del caso ilustrativo de 27 estudiantes y
tres cursos al variar los pesos de las dos componentes del objetivo:

$$
\min\; \lambda_0 F_1 + \lambda_1 F_2,
\qquad
F_1=|S|-\sum_i z_i,
\qquad
F_2=T.
$$

El texto listo para adaptar al manuscrito está en
[`analisis_sensibilidad_lambda.md`](analisis_sensibilidad_lambda.md).

## Resultado documentado

La frontera eficiente reportada contiene los puntos

$$
(F_1,T)\in\{(3,8/3),(1,14/3),(0,20/3)\},
$$

con quiebres en \(\lambda_0=1/2\) y \(\lambda_0=2/3\) bajo la normalización
\(\lambda_0+\lambda_1=1\).

## Trazabilidad

El repositorio todavía no incluye los scripts específicos, logs crudos ni
figuras utilizados para producir este barrido. Por lo tanto, el documento debe
considerarse material del manuscrito pendiente de completar con su paquete de
reproducibilidad antes de la entrega final.

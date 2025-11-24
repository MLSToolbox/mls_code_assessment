# Explicacion de lo que aun falta por agergar a la metrica FPC

Lo que falta agregar (que ya se contempla en el csv) al calculo es lo siguiente:
- ML CONTENT: Valor booleano que determine mediante heuristica (similar a pipeline_analyzer) si un archivo contiene codigo que no sea de ML; este puede ser por ejemplo codigo de tkinter para tener una vista.
- NLOC: Numero de lineas de codigo que hay en el archivo, esto debe ser un numero por ejemplo arriba de 30 lineas de codigo ya se considera que ese archivo supera el threshold. Este valor debe ser una constante que se pueda cambiar facilmente. El objetivo es que si se detecta 2 phases por ejemplo en un archivo de 30 lineas o menos se haga la observacion pero no se marque como poco cohesivo porque es muy pequeño.


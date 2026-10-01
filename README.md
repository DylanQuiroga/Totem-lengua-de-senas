# iDEV: Totem lengua de señas

## Idea

Nuestro proyecto “Traductor de lengua de señas", el cuál consiste en un tótem capaz de reconocer el lenguaje de señas usando una cámara y un modelo de inteligencia artificial. La idea es que el sistema pueda traducir los gestos a texto o voz, lo cual puede ser útil para personas con discapacidad auditiva. Para lograr esto estamos usando herramientas como MediaPipe y TensorFlow.

## Resultados obtenidos

* Pérdida (loss) de prueba: 0.1404
* Exactitud categórica (categorical_accuracy): 0.9203

## Funcionamiento del prototipo
* Seguimiento del rostro
* Deteccion de gesto
* Traduccion en tiempo real
* Botones de funcionalidad

## Conexiones (Raspberry pi 5)
* Servomotor: GPIO 14
* LED verde: GPIO 2
* LED rojo: GPIO 3
* Botón físico de borrado: GPIO 17
* Botón físico de lectura (TTS): GPIO 27
* 


![img1](https://media.canva.com/v2/image-resize/format:JPG/height:600/quality:92/uri:ifs%3A%2F%2FM%2F832ee548-4ea7-49a6-a54f-46efa5456493/watermark:F/width:800?csig=AAAAAAAAAAAAAAAAAAAAAFTO62tqSDxDn6m-QN0MsJmPtjn1cWGRI27vwuv4zlvZ&exp=1790829700&osig=AAAAAAAAAAAAAAAAAAAAACT_5Wo6XOU45EKATSqtx8R2lIstaitHztxuhrJuCq1Z&signer=media-rpc&x-canva-quality=screen)

import os
import cv2
import RPi.GPIO as GPIO
from time import sleep
import threading

class ServoControllerGPIO14:
    def __init__(self, pin=14):
        self.servo_pin = pin
        self.current_angle = 90
        self.target_angle = 90
        self.is_moving = False
        
        print(f"Inicializando servo en GPIO {pin}")
        
        # Configurar GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.servo_pin, GPIO.OUT)
        
        # PWM optimizado para GPIO 14
        self.pwm = GPIO.PWM(self.servo_pin, 50)
        self.pwm.start(0)
        
        # Posición inicial
        self.set_angle(90)
        sleep(1)
        self.pwm.ChangeDutyCycle(0)  # Detener para evitar temblores
        
        print("✓ Servo inicializado correctamente")
    
    def angle_to_duty_cycle(self, angle):
        """Convierte ángulo a duty cycle optimizado para GPIO 14"""
        angle = max(0, min(180, angle))
        # Rango ajustado para mejor precisión en GPIO 14
        duty = 2.0 + (angle / 180.0) * 10.5
        return duty
    
    def set_angle(self, angle):
        """Establece el ángulo del servo con suavizado"""
        angle = max(0, min(180, angle))
        
        # Solo mover si hay diferencia significativa
        if abs(angle - self.current_angle) < 3:
            return False
        
        # Movimiento suave
        steps = max(1, int(abs(angle - self.current_angle) / 10))
        step_size = (angle - self.current_angle) / steps
        
        for i in range(steps):
            intermediate_angle = self.current_angle + (step_size * (i + 1))
            duty = self.angle_to_duty_cycle(intermediate_angle)
            self.pwm.ChangeDutyCycle(duty)
            sleep(0.02)
        
        self.current_angle = angle
        
        # Pulso final para asegurar posición
        final_duty = self.angle_to_duty_cycle(angle)
        self.pwm.ChangeDutyCycle(final_duty)
        sleep(0.1)
        self.pwm.ChangeDutyCycle(0)  # Detener PWM
        
        return True
    
    def smooth_track(self, target_angle):
        """Seguimiento suave sin movimientos bruscos"""
        target_angle = max(0, min(180, target_angle))
        
        # Filtro de cambios muy pequeños
        if abs(target_angle - self.current_angle) < 2:
            return
        
        # Limitar velocidad de cambio
        max_change = 15  # Máximo cambio por frame
        angle_diff = target_angle - self.current_angle
        
        if abs(angle_diff) > max_change:
            if angle_diff > 0:
                target_angle = self.current_angle + max_change
            else:
                target_angle = self.current_angle - max_change
        
        self.set_angle(target_angle)
    
    def cleanup(self):
        """Limpieza segura del GPIO"""
        try:
            # Centrar servo antes de salir
            self.pwm.ChangeDutyCycle(7.5)  # 90 grados
            sleep(0.5)
            self.pwm.ChangeDutyCycle(0)
            self.pwm.stop()
            GPIO.cleanup()
            print("✓ GPIO limpiado correctamente")
        except Exception as e:
            print(f"Error durante limpieza: {e}")

def load_face_cascade():
    """Carga el clasificador de caras con rutas alternativas"""
    # Intentar diferentes rutas
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'haarcascade_frontalface_default.xml')
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            face_cascade = cv2.CascadeClassifier(path)
            if not face_cascade.empty():
                print(f"✓ Clasificador cargado desde: {path}")
                return face_cascade
    
    print("❌ No se pudo cargar el clasificador de caras")
    return None

def main():
    print("🎯 SEGUIMIENTO FACIAL CON SERVO EN GPIO 14")
    print("=" * 50)
    
    # Inicializar servo
    try:
        servo = ServoControllerGPIO14(pin=14)
    except Exception as e:
        print(f"❌ Error al inicializar servo: {e}")
        return
    
    # Cargar clasificador de caras
    face_cascade = load_face_cascade()
    if face_cascade is None:
        servo.cleanup()
        return
    
    # Inicializar cámara
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Error al abrir la cámara")
        servo.cleanup()
        return
    
    # Configurar cámara
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    # Parámetros de seguimiento optimizados
    zona_muerta = 50      # Zona central donde no se mueve el servo
    ganancia = 0.4        # Sensibilidad del seguimiento
    frame_skip = 0        # Contador para procesar cada N frames
    
    print("✓ Sistema iniciado")
    print("📹 Mueve tu cara para probar el seguimiento")
    print("⌨️  Controles: ESC=salir, C=centrar, R=reset")
    
    frame_count = 0
    no_face_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Error al capturar frame")
                break
            
            frame_count += 1
            
            # Procesar cada frame (no saltar frames para mejor seguimiento)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Detectar caras con parámetros optimizados
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=4,
                minSize=(60, 60),
                maxSize=(300, 300),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            frame_center_x = frame.shape[1] // 2
            
            if len(faces) > 0:
                no_face_count = 0
                
                # Seleccionar la cara más grande y centrada
                best_face = None
                best_score = 0
                
                for (x, y, w, h) in faces:
                    face_center_x = x + w // 2
                    size_score = w * h
                    center_score = 1000 / (1 + abs(face_center_x - frame_center_x))
                    total_score = size_score + center_score
                    
                    if total_score > best_score:
                        best_score = total_score
                        best_face = (x, y, w, h)
                
                if best_face:
                    x, y, w, h = best_face
                    face_center_x = x + w // 2
                    
                    # Calcular offset desde el centro
                    offset = face_center_x - frame_center_x
                    
                    # Solo mover si está fuera de la zona muerta
                    if abs(offset) > zona_muerta:
                        # Calcular nuevo ángulo del servo
                        angle_change = (offset / frame.shape[1]) * 90 * ganancia
                        new_angle = servo.current_angle - angle_change
                        
                        # Aplicar seguimiento suave
                        servo.smooth_track(new_angle)
                        
                        # Debug cada 30 frames
                        if frame_count % 30 == 0:
                            print(f"Siguiendo: offset={offset:+3.0f}px, servo={servo.current_angle:.1f}°")
                    
                    # Dibujar visualización
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.circle(frame, (face_center_x, y + h//2), 5, (255, 0, 0), -1)
                    cv2.putText(frame, f"Offset: {offset:+.0f}", (x, y-10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                no_face_count += 1
                # Auto-centrar después de 3 segundos sin cara
                if no_face_count > 90:  # 3 segundos a 30fps
                    servo.smooth_track(90)
                    no_face_count = 0
                    if frame_count % 90 == 0:
                        print("Sin cara detectada - Centrando servo")
            
            # Dibujar interfaz
            # Zona muerta
            cv2.line(frame, (frame_center_x - zona_muerta, 0), 
                    (frame_center_x - zona_muerta, frame.shape[0]), (255, 255, 0), 1)
            cv2.line(frame, (frame_center_x + zona_muerta, 0), 
                    (frame_center_x + zona_muerta, frame.shape[0]), (255, 255, 0), 1)
            
            # Línea central
            cv2.line(frame, (frame_center_x, 0), (frame_center_x, frame.shape[0]), (0, 0, 255), 2)
            
            # Información en pantalla
            cv2.putText(frame, f"Servo: {servo.current_angle:.1f}°", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, f"Caras: {len(faces)}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, f"GPIO: 14", (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            cv2.imshow("Seguimiento Facial - GPIO 14", frame)
            
            # Controles de teclado
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC para salir
                break
            elif key == ord('c') or key == ord('C'):  # Centrar
                print("🎯 Centrando servo...")
                servo.set_angle(90)
            elif key == ord('r') or key == ord('R'):  # Reset
                print("🔄 Reiniciando servo...")
                servo.set_angle(90)
                sleep(0.5)
            
            # Control de FPS
            sleep(0.02)  # ~50 FPS máximo
    
    except KeyboardInterrupt:
        print("\n🛑 Interrumpido por usuario")
    
    except Exception as e:
        print(f"❌ Error durante ejecución: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("🧹 Limpiando recursos...")
        servo.cleanup()
        cap.release()
        cv2.destroyAllWindows()
        print("✅ Limpieza completada")

if __name__ == "__main__":
    main()
import os
import cv2
import RPi.GPIO as GPIO
from time import sleep
import threading
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import queue

class ServoControllerGPIO14:
    def __init__(self, pin=14):
        self.servo_pin = pin
        self.current_angle = 90
        self.target_angle = 90
        self.is_moving = False
        self.start_time = time.time()
        self.movement_delay = 3.0
        
        print(f"Inicializando servo en GPIO {pin}")
        
        # Configurar GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.servo_pin, GPIO.OUT)
        
        # PWM optimizado para GPIO 14
        self.pwm = GPIO.PWM(self.servo_pin, 50)
        self.pwm.start(0)
        
        # Posición inicial fija a 90 grados
        print("Inicializando servo a 90 grados...")
        self.set_angle(90, force=True)
        sleep(1)
        self.pwm.ChangeDutyCycle(0)
        
        print("✓ Servo inicializado correctamente en 90°")
        print(f"⏱️  Servo se activará después de {self.movement_delay} segundos")
    
    def angle_to_duty_cycle(self, angle):
        """Convierte ángulo a duty cycle optimizado para GPIO 14"""
        angle = max(0, min(180, angle))
        duty = 2.0 + (angle / 180.0) * 10.5
        return duty
    
    def set_angle(self, angle, force=False):
        """Establece el ángulo del servo con suavizado mejorado"""
        angle = max(0, min(180, angle))
        
        if not force and (time.time() - self.start_time) < self.movement_delay:
            return False
        
        # Filtro más estricto para evitar movimientos innecesarios
        if abs(angle - self.current_angle) < 2:
            return False
        
        # Movimiento más suave y preciso
        steps = max(2, int(abs(angle - self.current_angle) / 8))
        step_size = (angle - self.current_angle) / steps
        
        for i in range(steps):
            intermediate_angle = self.current_angle + (step_size * (i + 1))
            duty = self.angle_to_duty_cycle(intermediate_angle)
            self.pwm.ChangeDutyCycle(duty)
            sleep(0.025)  # Movimiento más fluido
        
        self.current_angle = angle
        
        # Pulso final para asegurar posición
        final_duty = self.angle_to_duty_cycle(angle)
        self.pwm.ChangeDutyCycle(final_duty)
        sleep(0.1)
        self.pwm.ChangeDutyCycle(0)
        
        return True
    
    def smooth_track(self, target_angle):
        """Seguimiento suave con filtros avanzados"""
        target_angle = max(0, min(180, target_angle))
        
        if (time.time() - self.start_time) < self.movement_delay:
            return False
        
        # Filtro más estricto para cambios pequeños
        if abs(target_angle - self.current_angle) < 2.5:
            return False
        
        # Limitar velocidad de cambio - más conservador
        max_change = 15  # Reducido para movimientos más suaves
        angle_diff = target_angle - self.current_angle
        
        if abs(angle_diff) > max_change:
            if angle_diff > 0:
                target_angle = self.current_angle + max_change
            else:
                target_angle = self.current_angle - max_change
        
        self.set_angle(target_angle)
        return True
    
    def is_movement_enabled(self):
        """Verifica si el movimiento está habilitado"""
        return (time.time() - self.start_time) >= self.movement_delay
    
    def cleanup(self):
        """Limpieza segura del GPIO"""
        try:
            self.pwm.ChangeDutyCycle(7.5)  # 90 grados
            sleep(0.5)
            self.pwm.ChangeDutyCycle(0)
            self.pwm.stop()
            GPIO.cleanup()
            print("✓ GPIO limpiado correctamente")
        except Exception as e:
            print(f"Error durante limpieza: {e}")

class LEDController:
    def __init__(self, green_pin=2, red_pin=3):
        self.green_pin = green_pin
        self.red_pin = red_pin
        
        print(f"Inicializando LEDs: Verde GPIO{green_pin}, Rojo GPIO{red_pin}")
        
        GPIO.setup(self.green_pin, GPIO.OUT)
        GPIO.setup(self.red_pin, GPIO.OUT)
        
        self.set_no_gesture()
        print("✓ LEDs inicializados correctamente")
    
    def set_gesture_detected(self):
        """Enciende LED verde, apaga LED rojo"""
        GPIO.output(self.green_pin, GPIO.HIGH)
        GPIO.output(self.red_pin, GPIO.LOW)
    
    def set_no_gesture(self):
        """Enciende LED rojo, apaga LED verde"""
        GPIO.output(self.green_pin, GPIO.LOW)
        GPIO.output(self.red_pin, GPIO.HIGH)
    
    def cleanup(self):
        """Apaga todos los LEDs"""
        GPIO.output(self.green_pin, GPIO.LOW)
        GPIO.output(self.red_pin, GPIO.LOW)
        print("✓ LEDs apagados")

class ASLRecognizer:
    def __init__(self, model_path='gesture_recognizer.task'):
        self.model_path = model_path
        self.recognizer = None
        self.last_speech_time = 0
        self.speech_delay = 2.0
        self.last_gesture = ""
        
        print("MediaPipe version:", mp.__version__)
        
        try:
            base_options = python.BaseOptions(model_asset_path=self.model_path)
            options = vision.GestureRecognizerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE
            )
            self.recognizer = vision.GestureRecognizer.create_from_options(options)
            print("✓ Reconocedor ASL inicializado correctamente")
        except Exception as e:
            print(f"❌ Error al cargar el modelo ASL: {e}")
            self.recognizer = None
    
    def speak_gesture(self, gesture_name):
        """Función para reproducir la letra usando espeak en español"""
        try:
            print(f"Pronunciando: {gesture_name}")
            os.system(f'espeak -v es "{gesture_name}" 2>/dev/null')
        except Exception as e:
            print(f"Error TTS: {e}")
    
    def recognize_gesture(self, frame_rgb):
        """Reconoce gestos en el frame y retorna información"""
        if self.recognizer is None:
            return None, "Reconocedor no disponible", False
        
        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            result = self.recognizer.recognize(mp_image)
            
            if result.gestures:
                top_gesture = result.gestures[0][0]
                confidence = top_gesture.score
                current_time = time.time()
                
                if confidence > 0.7:
                    gesture_name = top_gesture.category_name
                    
                    if (gesture_name != self.last_gesture and 
                        current_time - self.last_speech_time > self.speech_delay):
                        self.speak_gesture(gesture_name)
                        self.last_speech_time = current_time
                        self.last_gesture = gesture_name
                    
                    return confidence, f"{gesture_name}", True
                else:
                    self.last_gesture = ""
                    return confidence, "Gesto no claro", False
            else:
                self.last_gesture = ""
                return 0.0, "Sin gesto detectado", False
                
        except Exception as e:
            print(f"Error en detección ASL: {e}")
            return None, "Error en detección", False

def load_face_cascade():
    """Carga el clasificador de caras con rutas alternativas"""
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

class ASLGui:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Reconocimiento ASL")
        self.root.geometry("800x700")
        self.root.configure(bg='#2c3e50')
        
        # Variables de control
        self.running = False
        self.cap = None
        self.servo = None
        self.led_controller = None
        self.asl_recognizer = None
        self.face_cascade = None
        
        # Cola para comunicación entre hilos
        self.update_queue = queue.Queue()
        
        # Variables de seguimiento
        self.zona_muerta_ampliada = 120
        self.zona_activacion_critica = 80
        self.ganancia_base = 0.4
        self.ganancia_critica = 0.7
        self.face_tracking_enabled = True
        
        self.setup_gui()
        self.init_components()
        
    def setup_gui(self):
        """Configura la interfaz gráfica"""
        # Título principal
        title_frame = tk.Frame(self.root, bg='#2c3e50')
        title_frame.pack(pady=10)
        
        title_label = tk.Label(title_frame, text="Sistema de Reconocimiento ASL", 
                              font=('Arial', 20, 'bold'), fg='white', bg='#2c3e50')
        title_label.pack()
        
        # Frame para la cámara
        self.camera_frame = tk.Frame(self.root, bg='#34495e', relief='sunken', bd=2)
        self.camera_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        # Label para mostrar el video
        self.video_label = tk.Label(self.camera_frame, bg='black')
        self.video_label.pack(expand=True, fill='both')
        
        # Frame inferior para controles y texto
        bottom_frame = tk.Frame(self.root, bg='#2c3e50')
        bottom_frame.pack(pady=10, padx=20, fill='x')
        
        # Frame para el texto interpretado
        text_frame = tk.Frame(bottom_frame, bg='#2c3e50')
        text_frame.pack(side='left', fill='both', expand=True)
        
        # Label para mostrar el gesto interpretado
        gesture_title = tk.Label(text_frame, text="Gesto Detectado:", 
                                font=('Arial', 12, 'bold'), fg='white', bg='#2c3e50')
        gesture_title.pack(anchor='w')
        
        self.gesture_label = tk.Label(text_frame, text="Sin gesto detectado", 
                                     font=('Arial', 16), fg='#ecf0f1', bg='#34495e',
                                     relief='sunken', bd=2, padx=10, pady=5)
        self.gesture_label.pack(fill='x', pady=5)
        
        # Label para mostrar la confianza
        self.confidence_label = tk.Label(text_frame, text="Confianza: 0%", 
                                        font=('Arial', 10), fg='#bdc3c7', bg='#2c3e50')
        self.confidence_label.pack(anchor='w')
        
        # Frame para botones
        button_frame = tk.Frame(bottom_frame, bg='#2c3e50')
        button_frame.pack(side='right', padx=(20, 0))
        
        # Botón TTS (para futuro)
        self.tts_button = tk.Button(button_frame, text="🔊 TTS", 
                                   font=('Arial', 12, 'bold'), bg='#3498db', fg='white',
                                   relief='raised', bd=2, padx=20, pady=10,
                                   state='disabled')  # Deshabilitado por ahora
        self.tts_button.pack(pady=5)
        
        # Botón de control principal
        self.control_button = tk.Button(button_frame, text="▶ Iniciar", 
                                       font=('Arial', 12, 'bold'), bg='#27ae60', fg='white',
                                       relief='raised', bd=2, padx=20, pady=10,
                                       command=self.toggle_system)
        self.control_button.pack(pady=5)
        
        # Botón centrar servo
        self.center_button = tk.Button(button_frame, text="⚪ Centrar", 
                                      font=('Arial', 10), bg='#f39c12', fg='white',
                                      relief='raised', bd=2, padx=15, pady=5,
                                      command=self.center_servo)
        self.center_button.pack(pady=2)
        
        # Frame para información del sistema
        info_frame = tk.Frame(self.root, bg='#2c3e50')
        info_frame.pack(pady=5, padx=20, fill='x')
        
        # Labels de estado
        self.status_label = tk.Label(info_frame, text="Estado: Detenido", 
                                    font=('Arial', 10), fg='#e74c3c', bg='#2c3e50')
        self.status_label.pack(side='left')
        
        self.servo_label = tk.Label(info_frame, text="Servo: 90°", 
                                   font=('Arial', 10), fg='#95a5a6', bg='#2c3e50')
        self.servo_label.pack(side='right')
        
    def init_components(self):
        """Inicializa los componentes del sistema"""
        try:
            print("Inicializando componentes del sistema...")
            self.servo = ServoControllerGPIO14(pin=14)
            self.led_controller = LEDController(green_pin=2, red_pin=3)
            self.asl_recognizer = ASLRecognizer()
            self.face_cascade = load_face_cascade()
            
            if self.face_cascade is None:
                print("⚠️  Continuando sin seguimiento facial...")
                
            print("✓ Componentes inicializados correctamente")
            
        except Exception as e:
            print(f"❌ Error al inicializar componentes: {e}")
            messagebox.showerror("Error", f"Error al inicializar componentes:\n{e}")
    
    def toggle_system(self):
        """Inicia o detiene el sistema"""
        if not self.running:
            self.start_system()
        else:
            self.stop_system()
    
    def start_system(self):
        """Inicia el sistema de reconocimiento"""
        try:
            # Inicializar cámara
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                messagebox.showerror("Error", "No se pudo abrir la cámara")
                return
            
            # Configuración de cámara optimizada
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            self.running = True
            self.control_button.config(text="⏸ Detener", bg='#e74c3c')
            self.status_label.config(text="Estado: Ejecutándose", fg='#27ae60')
            
            # Iniciar hilo de procesamiento
            self.processing_thread = threading.Thread(target=self.process_video, daemon=True)
            self.processing_thread.start()
            
            # Iniciar actualización de GUI
            self.update_gui()
            
            print("✓ Sistema iniciado correctamente")
            
        except Exception as e:
            print(f"❌ Error al iniciar sistema: {e}")
            messagebox.showerror("Error", f"Error al iniciar sistema:\n{e}")
    
    def stop_system(self):
        """Detiene el sistema"""
        self.running = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.control_button.config(text="▶ Iniciar", bg='#27ae60')
        self.status_label.config(text="Estado: Detenido", fg='#e74c3c')
        self.video_label.config(image='', bg='black')
        self.gesture_label.config(text="Sin gesto detectado", bg='#34495e')
        self.confidence_label.config(text="Confianza: 0%")
        
        print("✓ Sistema detenido")
    
    def center_servo(self):
        """Centra el servo"""
        if self.servo:
            self.servo.set_angle(90)
            print("🎯 Servo centrado")
    
    def process_video(self):
        """Procesa el video en un hilo separado"""
        frame_count = 0
        no_face_count = 0
        asl_process_interval = 4
        face_process_interval = 2
        last_debug_time = 0
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                frame_count += 1
                frame = cv2.flip(frame, 1)
                frame_center_x = frame.shape[1] // 2
                frame_width = frame.shape[1]
                
                # === RECONOCIMIENTO ASL ===
                gesture_text = "Procesando..."
                confidence = 0.0
                gesture_detected = False
                
                if frame_count % asl_process_interval == 0:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    confidence, gesture_text, gesture_detected = self.asl_recognizer.recognize_gesture(frame_rgb)
                    
                    # Control de LEDs
                    if gesture_detected and confidence > 0.7:
                        self.led_controller.set_gesture_detected()
                    else:
                        self.led_controller.set_no_gesture()
                    
                    # Enviar actualización a la GUI
                    self.update_queue.put(('gesture', gesture_text, confidence, gesture_detected))
                
                # === SEGUIMIENTO FACIAL (sin visualización) ===
                if self.face_cascade is not None and self.face_tracking_enabled and frame_count % face_process_interval == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.equalizeHist(gray)
                    
                    scale_factor = 0.6
                    small_gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor)
                    
                    small_faces = self.face_cascade.detectMultiScale(
                        small_gray,
                        scaleFactor=1.15,
                        minNeighbors=4,
                        minSize=(25, 25),
                        maxSize=(120, 120),
                        flags=cv2.CASCADE_SCALE_IMAGE | cv2.CASCADE_DO_CANNY_PRUNING
                    )
                    
                    faces = []
                    for (x, y, w, h) in small_faces:
                        faces.append((int(x/scale_factor), int(y/scale_factor), 
                                    int(w/scale_factor), int(h/scale_factor)))
                    
                    if len(faces) > 0:
                        no_face_count = 0
                        
                        # Selección de la mejor cara
                        best_face = None
                        best_score = 0
                        
                        for (x, y, w, h) in faces:
                            face_center_x = x + w // 2
                            size_score = w * h
                            center_score = 2000 / (1 + abs(face_center_x - frame_center_x))
                            vertical_bonus = 500 if frame.shape[0] // 3 < y + h//2 < 2 * frame.shape[0] // 3 else 0
                            total_score = size_score + center_score + vertical_bonus
                            
                            if total_score > best_score:
                                best_score = total_score
                                best_face = (x, y, w, h)
                        
                        if best_face:
                            x, y, w, h = best_face
                            face_center_x = x + w // 2
                            offset = face_center_x - frame_center_x
                            
                            # Lógica de seguimiento (sin visualización)
                            should_move = False
                            ganancia_actual = self.ganancia_base
                            
                            if abs(offset) > self.zona_muerta_ampliada:
                                should_move = True
                                
                                if abs(offset) > (frame_width // 2 - self.zona_activacion_critica):
                                    ganancia_actual = self.ganancia_critica
                            
                            if should_move and self.servo.is_movement_enabled():
                                angle_change = (offset / frame_width) * 90 * ganancia_actual
                                new_angle = self.servo.current_angle + angle_change
                                
                                if self.servo.smooth_track(new_angle):
                                    current_time = time.time()
                                    if current_time - last_debug_time > 2.0:
                                        direction = "→" if offset > 0 else "←"
                                        print(f"🎯 Siguiendo {direction}: offset={offset:+4.0f}px, servo={self.servo.current_angle:.1f}°")
                                        last_debug_time = current_time
                    else:
                        no_face_count += 1
                        if no_face_count > 90 and self.servo.is_movement_enabled():
                            self.servo.smooth_track(90)
                            no_face_count = 0
                            print("❌ Sin cara detectada - Centrando servo")
                
                # Enviar frame a la GUI (sin líneas de seguimiento)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.update_queue.put(('frame', frame_rgb))
                
                # Enviar información del servo
                if frame_count % 10 == 0:  # Cada 10 frames
                    self.update_queue.put(('servo', self.servo.current_angle))
                
                sleep(0.012)  # Control de FPS
                
            except Exception as e:
                print(f"Error en procesamiento: {e}")
                break
    
    def update_gui(self):
        """Actualiza la GUI con los datos del hilo de procesamiento"""
        try:
            while not self.update_queue.empty():
                data = self.update_queue.get_nowait()
                
                if data[0] == 'frame':
                    # Actualizar frame de video
                    frame_rgb = data[1]
                    image = Image.fromarray(frame_rgb)
                    image = image.resize((640, 480), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(image)
                    self.video_label.config(image=photo)
                    self.video_label.image = photo  # Mantener referencia
                    
                elif data[0] == 'gesture':
                    # Actualizar información del gesto
                    gesture_text, confidence, gesture_detected = data[1], data[2], data[3]
                    
                    if confidence is not None and confidence > 0.7:
                        self.gesture_label.config(text=gesture_text, bg='#27ae60')
                        self.confidence_label.config(text=f"Confianza: {confidence:.0%}", fg='#27ae60')
                    elif confidence is not None:
                        self.gesture_label.config(text=gesture_text, bg='#f39c12')
                        self.confidence_label.config(text=f"Confianza: {confidence:.0%}", fg='#f39c12')
                    else:
                        self.gesture_label.config(text="Error en detección", bg='#e74c3c')
                        self.confidence_label.config(text="Confianza: 0%", fg='#e74c3c')
                
                elif data[0] == 'servo':
                    # Actualizar información del servo
                    servo_angle = data[1]
                    self.servo_label.config(text=f"Servo: {servo_angle:.1f}°")
                    
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error actualizando GUI: {e}")
        
        if self.running:
            self.root.after(50, self.update_gui)  # Actualizar cada 50ms
    
    def on_closing(self):
        """Maneja el cierre de la aplicación"""
        print("Cerrando aplicación...")
        self.running = False
        
        if self.cap:
            self.cap.release()
        
        if self.led_controller:
            self.led_controller.cleanup()
        
        if self.servo:
            self.servo.cleanup()
        
        self.root.destroy()

def main():
    print("🎯 SISTEMA ASL CON INTERFAZ GRÁFICA")
    print("=" * 50)
    
    root = tk.Tk()
    app = ASLGui(root)
    
    # Configurar el cierre de la aplicación
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n🛑 Interrumpido por usuario")
        app.on_closing()

if __name__ == "__main__":
    main()
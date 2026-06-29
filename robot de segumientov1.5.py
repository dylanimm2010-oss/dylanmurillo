import time
import board
import digitalio
import pwmio
from ideaboard import IdeaBoard
import adafruit_dht  # 👈 Volvemos a traer la librería del clima

ib = IdeaBoard()

# 1. CONFIGURACIÓN DEL SWITCH (Protección contra reinicios)
switch = digitalio.DigitalInOut(board.IO27)
switch.direction = digitalio.Direction.INPUT
switch.pull = digitalio.Pull.DOWN

# 2. CONFIGURACIÓN DE LOS 2 INFRARROJOS LATERALES
ir_izquierdo = digitalio.DigitalInOut(board.IO32)
ir_izquierdo.direction = digitalio.Direction.INPUT

ir_derecho = digitalio.DigitalInOut(board.IO33)
ir_derecho.direction = digitalio.Direction.INPUT

# 3. CONFIGURACIÓN DEL SENSOR DE CLIMA DHT22 (Pin IO26)
try:
    sensor_clima = adafruit_dht.DHT22(board.IO26)
except Exception:
    print("Aviso: No se detectó el DHT22 al arrancar, revisa cables.")

# 4. CONFIGURACIÓN DEL PARLANTE (Hardware PWM nativo)
parlante = pwmio.PWMOut(board.IO25, variable_frequency=True)

# Función afinada para la música de Iron Man
def tocar_nota(frecuencia, duracion):
    if frecuencia == 0:
        parlante.duty_cycle = 0
    else:
        parlante.frequency = frecuencia
        parlante.duty_cycle = 32768
    time.sleep(duracion)
    parlante.duty_cycle = 0
    time.sleep(0.03)

# El robot arranca tocando la canción para lucirse ante el profesor
print("--- Tocando Intro de Iron Man limpia ---")
tocar_nota(494, 0.6)  # Si
tocar_nota(587, 0.6)  # Re
tocar_nota(587, 0.3)  # Re
tocar_nota(659, 0.3)  # Mi
tocar_nota(659, 0.6)  # Mi

tocar_nota(784, 0.15) # Sol
tocar_nota(740, 0.15) # Fa#
tocar_nota(784, 0.15) # Sol
tocar_nota(740, 0.15) # Fa#
tocar_nota(784, 0.15) # Sol
tocar_nota(740, 0.15) # Fa#

tocar_nota(587, 0.3)  # Re
tocar_nota(587, 0.3)  # Re
tocar_nota(659, 0.3)  # Mi
tocar_nota(659, 0.6)  # Mi

print("--- ¡Robot Inicializado con Éxito! ---")
print("Esperando a que enciendas el Switch de la línea 27...")

while True:
    # --- LEER TEMPERATURA Y HUMEDAD SIEMPRE (Esté el switch encendido o no) ---
    try:
        temperatura = sensor_clima.temperature
        humedad = sensor_clima.humidity
        txt_clima = f"Temp: {temperatura:.1f}C | Hum: {humedad:.1f}%"
    except RuntimeError:
        # El DHT22 es lento, si da error de lectura ponemos esto para que no se caiga el código
        txt_clima = "Temp: Leyendo... | Hum: Leyendo..."
    except Exception:
        txt_clima = "Temp: --C | Hum: --%"

    # --- CONTROL DEL ROBOT SEGÚN EL SWITCH ---
    if switch.value:
        lectura_izq = ir_izquierdo.value
        lectura_der = ir_derecho.value
        
        # Mostramos el clima y los sensores en la consola serie
        print(f"{txt_clima} | Switch: ON | IZQ: {lectura_izq} | DER: {lectura_der}")

        # LÓGICA DE SEGUIMIENTO CON DOS SENSORES
        if lectura_izq == lectura_der:
            ib.motor_1.throttle = 0.5
            ib.motor_2.throttle = 0.5
        elif lectura_izq == True and lectura_der == False:
            ib.motor_1.throttle = 0.5
            ib.motor_2.throttle = 0.0
        elif lectura_izq == False and lectura_der == True:
            ib.motor_1.throttle = 0.0
            ib.motor_2.throttle = 0.5
                
    else:
        # Si el switch está apagado, el robot no se mueve pero sigue imprimiendo el clima
        print(f"{txt_clima} | Switch: APAGADO -> Motores bloqueados")
        ib.motor_1.throttle = 0.0
        ib.motor_2.throttle = 0.0
        
    time.sleep(0.2)  # Pausa de 0.2 para darle un respiro al sensor DHT22
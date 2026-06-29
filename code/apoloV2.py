import ssl
import socketpool
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT
from random import randint  
from ideaboard import IdeaBoard
import time
import board
import adafruit_dht
import digitalio
import pwmio

ib = IdeaBoard()

# Configuración de pines de entrada y salida
switch = digitalio.DigitalInOut(board.IO27)
switch.direction = digitalio.Direction.INPUT
switch.pull = digitalio.Pull.DOWN

ir_izquierdo = digitalio.DigitalInOut(board.IO32)
ir_izquierdo.direction = digitalio.Direction.INPUT

ir_derecho = digitalio.DigitalInOut(board.IO33)
ir_derecho.direction = digitalio.Direction.INPUT

sensor_clima = None
try:
    sensor_clima = adafruit_dht.DHT22(board.IO26)
except Exception:
    print("Aviso: No se detectó el DHT22.")

parlante = pwmio.PWMOut(board.IO25, variable_frequency=True)

def tocar_nota(frecuencia, duracion):
    if frecuencia == 0:
        parlante.duty_cycle = 0
    else:
        parlante.frequency = frecuencia  
        parlante.duty_cycle = 32768
    time.sleep(duracion)
    parlante.duty_cycle = 0
    time.sleep(0.03)

# Conexión red WiFi
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py!")
    raise

print("Connecting to %s" % secrets["ssid"])
wifi.radio.connect(secrets["ssid"], secrets["password"])
print("Connected to %s!" % secrets["ssid"])

aio_username = secrets["aio_username"]
aio_key = secrets["aio_key"]

# Configuración de Adafruit IO
def connected(client):
    print("Connected to Adafruit IO!")
    client.subscribe("temp")
    client.subscribe("humid")
    client.subscribe("switch-virtual")
    client.subscribe("estado")
    client.subscribe("ENCENDIDO")

def disconnected(client):
    print("Disconnected from Adafruit IO!")

def message(client, feed_id, payload):
    pass

pool = socketpool.SocketPool(wifi.radio)
mqtt_client = MQTT.MQTT(
    broker="io.adafruit.com",
    port=1883,
    username=secrets["aio_username"],
    password=secrets["aio_key"],
    socket_pool=pool,
    ssl_context=ssl.create_default_context(),
)

io = IO_MQTT(mqtt_client)
io.on_connect = connected
io.on_disconnect = disconnected
io.on_message = message

print("Connecting to Adafruit IO...")
io.connect()

# Melodía de inicio
print("--- Tocando Melodía de Inicio ---")
tocar_nota(523, 0.15)  # Do
tocar_nota(659, 0.15)  # Mi
tocar_nota(784, 0.15)  # Sol
tocar_nota(1047, 0.5)  # Do Alto
print("--- Fin de la melodía ---")

# Variables de control
cronometro_clima = 0
ultimo_texto_enviado = ""
ultimo_switch_enviado = -1

# Variables globales para el diagnóstico del clima
diagnostico_temp = "Desconocido"
diagnostico_hum = "Desconocido"

print("Sistema listo.")

while True:
    try:
        io.loop()
    except Exception:
        try:
            io.connect()
        except Exception:
            pass

    # Lógica de movimiento y sonido
    movimiento = "Detenido"
    
    if switch.value:
        lectura_izq = ir_izquierdo.value
        lectura_der = ir_derecho.value
        
        if lectura_izq == lectura_der:
            movimiento = "Avanzando Recto"
            ib.motor_1.throttle = 0.5
            ib.motor_2.throttle = 0.5
           
            tocar_nota(523, 0.05)  
            tocar_nota(659, 0.05)  
            tocar_nota(784, 0.05)  
            tocar_nota(659, 0.05)  
        elif lectura_izq == True and lectura_der == False:
            movimiento = "Girando Izquierda"
            ib.motor_1.throttle = 0.5
            ib.motor_2.throttle = 0.0
            
            tocar_nota(698, 0.08)  
            tocar_nota(587, 0.08)  
        elif lectura_izq == False and lectura_der == True:
            movimiento = "Girando Derecha"
            ib.motor_1.throttle = 0.0
            ib.motor_2.throttle = 0.5
            
            tocar_nota(587, 0.08)  
            tocar_nota(698, 0.08)  
    else:
        # Acción inmediata al chocar: Retroceder durante medio segundo
        movimiento = "Retrocediendo por Obstaculo"
        print("--- Colision Detectada: Retrocediendo ---")
        
        # Motores hacia atrás
        ib.motor_1.throttle = -0.5
        ib.motor_2.throttle = -0.5
        
        # Pitido rápido de alerta mientras va hacia atrás
        tocar_nota(880, 0.1)   
        time.sleep(0.05)       
        tocar_nota(880, 0.1)   
        time.sleep(0.25)  # Completa el tiempo de retroceso
        
        # Frenar por completo antes de volver a evaluar
        ib.motor_1.throttle = 0.0
        ib.motor_2.throttle = 0.0
        movimiento = "Detenido por Switch"
        time.sleep(0.5)

    # Combinación de movimiento y estado del clima para el Dashboard
    texto_estado_actual = f"{movimiento} | Clima: {diagnostico_temp} y {diagnostico_hum}"

    # Transmisión inmediata por cambio de estado
    try:
        valor_sw_actual = 1 if switch.value else 0
        if valor_sw_actual != ultimo_switch_enviado:
            io.publish("switch-virtual", valor_sw_actual)
            ultimo_switch_enviado = valor_sw_actual
            print(f"Cambio Switch: {valor_sw_actual}")

        if texto_estado_actual != ultimo_texto_enviado:
            io.publish("estado", texto_estado_actual)
            ultimo_texto_enviado = texto_estado_actual
            print(f"Cambio Estado: {texto_estado_actual}")
            
    except Exception:
        print("Error en transmisión rápida.")

    # Lectura de clima y diagnóstico cada 12 segundos
    tiempo_ahora = time.monotonic()
    if (tiempo_ahora - cronometro_clima) >= 12:
        try:
            temp = None
            hum = None
            if sensor_clima is not None:
                try:
                    temp = sensor_clima.temperature
                    hum = sensor_clima.humidity
                except RuntimeError:
                    pass

            if temp is not None and hum is not None:
                # Diagnóstico térmico
                if temp < 18.0:
                    diagnostico_temp = "Frio"
                elif temp > 26.0:
                    diagnostico_temp = "Caluroso"
                else:
                    diagnostico_temp = "Templado"

                # Diagnóstico humedad
                if hum < 40.0:
                    diagnostico_hum = "Seco"
                elif hum > 75.0:
                    diagnostico_hum = "Humedo"
                else:
                    diagnostico_hum = "Normal"

                print(f"Datos -> Temp: {temp}C ({diagnostico_temp}) | Hum: {hum}% ({diagnostico_hum})")
                print(f"Ambiente: {diagnostico_temp} y {diagnostico_hum}")
                
                io.publish("temp", int(temp))
                io.publish("humid", int(hum))
                
            io.publish("ENCENDIDO", randint(0, 100))
        except Exception:
            print("Error en lectura o envío periódico.")
            
        cronometro_clima = tiempo_ahora
        
    time.sleep(0.1)

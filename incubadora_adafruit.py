import time
import board
import digitalio
import adafruit_dht
from ideaboard import IdeaBoard

# ======== Sensores y actuadores locales ========
dhtDevice = adafruit_dht.DHT11(board.IO26)

relay = digitalio.DigitalInOut(board.IO25)
relay.direction = digitalio.Direction.OUTPUT
RELAY_ACTIVE_LOW = False

def relay_on():
    relay.value = False if RELAY_ACTIVE_LOW else True

def relay_off():
    relay.value = True if RELAY_ACTIVE_LOW else False

ib = IdeaBoard()

TEMP_TARGET = 37.5
HUMIDITY_TARGET = 55.0

MOTOR_ON_SECONDS = 60
MOTOR_OFF_SECONDS = 300

motor_last_change = time.monotonic()
motor_running = True
ib.motor_1.throttle = 1.0
ib.motor_2.throttle = 1.0
print("Motor arrancó girando")

# ======== Adafruit IO ========
import ssl
import socketpool
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

print("Connecting to %s" % secrets["ssid"])
wifi.radio.connect(secrets["ssid"], secrets["password"])
print("Connected to %s!" % secrets["ssid"])

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

# Estados controlados por toggles
motor_auto = True   # True = AUTO, False = apagado forzado
relay_auto = True   # True = AUTO, False = apagado forzado

def connected(client):
    print("Conectado a Adafruit IO")
    client.subscribe("motorcontrol")  # toggle ON=auto, OFF=off
    client.subscribe("relaycontrol")  # toggle ON=auto, OFF=off

def message(client, feed_id, payload):
    global motor_auto, relay_auto
    print("Mensaje de", feed_id, ":", payload)
    # Toggle ON = AUTO, OFF = OFF
    if feed_id == "motorcontrol":
        motor_auto = (payload == "ON")
    if feed_id == "relaycontrol":
        relay_auto = (payload == "ON")

io.on_connect = connected
io.on_message = message
io.connect()

# ======== Bucle principal ========
last_publish = 0

while True:
    io.loop()

    # ---- Leer sensor DHT11 ----
    try:
        temp_c = dhtDevice.temperature
        humidity = dhtDevice.humidity
        print("Temperatura: {:.1f} °C   Humedad: {:.1f} %".format(temp_c, humidity))
    except RuntimeError as error:
        print("Error leyendo DHT11:", error.args[0])
        time.sleep(2)
        continue

    # ---- Control relé ----
    if relay_auto:
        if (temp_c < TEMP_TARGET) or (humidity < HUMIDITY_TARGET):
            relay_on()
            print("Relé encendido (auto)")
        else:
            relay_off()
            print("Relé apagado (auto)")
    else:
        relay_off()
        print("Relé forzado OFF")

    # ---- Control motor ----
    now = time.monotonic()
    if motor_auto:
        if motor_running:
            if now - motor_last_change >= MOTOR_ON_SECONDS:
                ib.motor_1.throttle = 0
                ib.motor_2.throttle = 0
                motor_running = False
                motor_last_change = now
                print("Motor detenido")
        else:
            if now - motor_last_change >= MOTOR_OFF_SECONDS:
                ib.motor_1.throttle = 1.0
                ib.motor_2.throttle = 1.0
                motor_running = True
                motor_last_change = now
                print("Motor girando")
    else:
        ib.motor_1.throttle = 0
        ib.motor_2.throttle = 0
        print("Motor forzado OFF")

    # ---- Calcular tiempo restante y convertir a mm:ss ----
    if motor_auto:
        if motor_running:
            time_left = MOTOR_ON_SECONDS - (now - motor_last_change)
        else:
            time_left = MOTOR_OFF_SECONDS - (now - motor_last_change)
    else:
        time_left = 0

    minutes = int(time_left) // 60
    seconds = int(time_left) % 60
    time_str = f"{minutes}:{seconds:02d}"  # Formato "mm:ss"

    # ---- Publicar a Adafruit IO cada 5 s ----
    if (time.monotonic() - last_publish) > 5:
        io.publish("temp", temp_c)
        io.publish("humid", humidity)
        io.publish("motortime", time_str)  # Formato mm:ss para Text Block
        last_publish = time.monotonic()

    time.sleep(2)
 
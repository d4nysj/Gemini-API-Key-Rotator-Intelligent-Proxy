import requests
import json
import time

# Apuntamos a tu Proxy Local. 
# Nota: Ponemos 'gemini-2.5-flash' en la URL porque tu script original lo pediría así,
# pero recuerda que el Proxy cambiará este modelo automáticamente por los de tu base de datos si este falla.
PROXY_URL = "http://127.0.0.1:5005/proxy/v1beta/models/gemini-2.5-flash:generateContent"

def probar_proxy_inteligente():
    print("🚀 Iniciando prueba del Proxy Inteligente (Base de Datos)...\n")
    
    payload = {
        "contents": [{
            "parts": [{"text": "Dime un dato muy curioso sobre la inteligencia artificial en una sola frase."}]
        }]
    }

    print(f"📡 Solicitando a través del Proxy: {PROXY_URL}")
    print("⏳ El proxy buscará llaves y modelos en tu base de datos local...")
    
    tiempo_inicio = time.time()
    
    try:
        respuesta = requests.post(
            PROXY_URL, 
            headers={'Content-Type': 'application/json'}, 
            json=payload,
            timeout=30 # Le damos más tiempo por si el proxy tiene que reintentar con varios modelos
        )
        
        tiempo_total = round(time.time() - tiempo_inicio, 2)
        
        print("\n" + "=" * 50)
        print(f"✅ ESTADO HTTP: {respuesta.status_code}")
        print(f"⏱️  TIEMPO TOTAL: {tiempo_total} segundos")
        print("=" * 50)

        if respuesta.status_code == 200:
            datos = respuesta.json()
            # Navegamos por el JSON de Google para sacar solo el texto de la IA
            texto_ia = datos['candidates'][0]['content']['parts'][0]['text']
            
            print("\n🤖 RESPUESTA RECIBIDA:")
            print(f"   {texto_ia.strip()}")
            print("\n🎉 ¡ÉXITO! El proxy ha gestionado la API Key y el modelo correctamente.")
            
        else:
            print("\n❌ HUBO UN PROBLEMA:")
            try:
                error_data = respuesta.json()
                print(json.dumps(error_data, indent=2))
            except json.JSONDecodeError:
                print(respuesta.text)
                
            print("\n💡 PISTA: Comprueba en la web (Puerto 5005) que tienes al menos UNA Key válida y UN modelo añadido.")

    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: No me puedo conectar al proxy. ¿Está el servicio ejecutándose?")
        print("   Comprueba con: systemctl status geminikeys")
        
    except requests.exceptions.Timeout:
        print("\n⏱️ ERROR: Timeout. El proxy tardó más de 30 segundos en probar todas las combinaciones posibles.")

if __name__ == "__main__":
    probar_proxy_inteligente()

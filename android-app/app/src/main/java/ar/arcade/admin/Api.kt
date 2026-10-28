package ar.arcade.admin

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Cliente mínimo de la API admin del arcade (HttpURLConnection + org.json, sin dependencias). */
class ApiException(msg: String, val code: Int = 0) : Exception(msg)

class Api(private val host: String, private val key: String) {
    val base: String get() = if (host.startsWith("http")) host.trimEnd('/') else "http://" + host.trimEnd('/')

    private fun request(method: String, path: String, body: String? = null): ByteArray {
        var lastErr: Exception? = null
        repeat(2) { attempt ->   // 1 reintento ante error de red
            try {
                val c = URL(base + path).openConnection() as HttpURLConnection
                c.requestMethod = method
                c.connectTimeout = 5000; c.readTimeout = 10000
                c.setRequestProperty("X-Admin-Key", key)
                if (body != null) {
                    c.doOutput = true
                    c.setRequestProperty("Content-Type", "application/json")
                    c.outputStream.use { it.write(body.toByteArray()) }
                }
                val code = c.responseCode
                if (code in 200..299) return c.inputStream.use { it.readBytes() }
                throw ApiException(when (code) {
                    401 -> "Clave de administrador incorrecta"
                    403 -> "Acceso denegado: conectate al WiFi del local"
                    422 -> "Dato inválido"
                    404 -> "Función no disponible en esta versión del servidor"
                    else -> "Error del servidor ($code)"
                }, code)
            } catch (e: ApiException) { throw e
            } catch (e: Exception) { lastErr = e; if (attempt == 0) Thread.sleep(500) }
        }
        throw ApiException("No se pudo conectar con la PC del arcade (${lastErr?.javaClass?.simpleName}). ¿Está prendida y en el mismo WiFi?")
    }

    private fun json(m: String, p: String, b: String? = null) = JSONObject(String(request(m, p, b)))

    fun stats() = json("GET", "/api/admin/stats")
    fun status() = json("GET", "/api/admin/status")
    fun payments(limit: Int = 100) = json("GET", "/api/admin/payments?limit=$limit").getJSONArray("items")
    fun setPrice(p: Double) = json("PUT", "/api/admin/price", JSONObject().put("price", p).toString()).getDouble("price")
    /** Alertas. Devuelve null si el servidor todavía no tiene el endpoint (404).
     *  Acepta tanto una lista JSON directa como {"items":[...]} / {"alertas":[...]}. */
    fun alertas(desdeId: Long = 0): JSONArray? {
        val raw = try { String(request("GET", "/api/admin/alertas?desde_id=$desdeId")).trim() }
                  catch (e: ApiException) { if (e.code == 404) return null else throw e }
        if (raw.startsWith("[")) return JSONArray(raw)
        val o = JSONObject(raw)
        return o.optJSONArray("items") ?: o.optJSONArray("alertas") ?: JSONArray()
    }
    fun marcarLeidas() { try { request("POST", "/api/admin/alertas/marcar_leidas", "{}") } catch (e: ApiException) { if (e.code != 404) throw e } }

    fun qrPng(): ByteArray = request("GET", "/api/admin/qr.png")
    fun printPageUrl() = "$base/admin/qr/imprimir?key=" + java.net.URLEncoder.encode(key, "UTF-8")
}

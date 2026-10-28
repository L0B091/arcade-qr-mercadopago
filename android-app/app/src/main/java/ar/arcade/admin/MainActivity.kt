package ar.arcade.admin

import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.os.Build
import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.print.PrintHelper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.text.NumberFormat
import java.util.Locale

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = Prefs(this)
        Vigilante.createChannel(this); Vigilante.schedule(this)
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        val start = if (intent?.getStringExtra("tab") == "ALERTAS") Tab.ALERT else null
        setContent { ArcadeTheme { App(prefs, start) } }
    }
}

enum class Tab(val label: String) { DASH("INICIO"), HIST("PAGOS"), PRICE("PRECIO"), ALERT("ALERTAS"), CONF("CONFIG") }

fun money(v: Double): String = "$" + NumberFormat.getIntegerInstance(Locale("es", "AR")).format(v.toLong())

suspend fun <T> io(block: () -> T): Result<T> = withContext(Dispatchers.IO) { runCatching(block) }

@Composable
fun App(prefs: Prefs, start: Tab? = null) {
    var tab by remember { mutableStateOf(start ?: if (prefs.configured) Tab.DASH else Tab.CONF) }
    val ctx = LocalContext.current
    LaunchedEffect(Unit) { while (true) { io { Vigilante.check(ctx) }; delay(60_000) } }  // chequeo rápido con la app abierta
    var api by remember { mutableStateOf(Api(prefs.host, prefs.key)) }
    Column(Modifier.fillMaxSize().background(DeepBlue).scanlines().systemBarsPadding()) {
        Text("★ ARCADE ADMIN ★", style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(16.dp).align(androidx.compose.ui.Alignment.CenterHorizontally))
        Box(Modifier.weight(1f).padding(horizontal = 12.dp)) {
            when (tab) {
                Tab.DASH -> Dashboard(api) { tab = Tab.ALERT }
                Tab.ALERT -> AlertsScreen(api)
                Tab.HIST -> History(api)
                Tab.PRICE -> PriceScreen(api)
                Tab.CONF -> ConfigScreen(prefs) { api = Api(prefs.host, prefs.key); tab = Tab.DASH }
            }
        }
        Row(Modifier.fillMaxWidth().background(Color.Black).padding(4.dp)) {
            Tab.values().forEach { t ->
                TextButton(onClick = { tab = t }, modifier = Modifier.weight(1f)) {
                    Text(t.label, style = MaterialTheme.typography.bodySmall.copy(color = if (t == tab) Orange else Color.White))
                }
            }
        }
    }
}

@Composable
fun ErrorText(e: String?) { if (e != null) Text("✖ $e", color = Red, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 6.dp)) }

@Composable
fun Dashboard(api: Api, openAlerts: () -> Unit) {
    var unread by remember { mutableStateOf(0) }
    var stats by remember { mutableStateOf<JSONObject?>(null) }
    var status by remember { mutableStateOf<JSONObject?>(null) }
    var last by remember { mutableStateOf<JSONObject?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    var tick by remember { mutableStateOf(0) }
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    LaunchedEffect(api, tick) {
        while (true) {   // auto-refresh cada 15 s
            loading = true
            io { Triple(api.stats(), api.status(), api.payments(1)) }
                .onSuccess { stats = it.first; status = it.second; last = it.third.optJSONObject(0); err = null }
                .onFailure { err = it.message }
            io { api.alertas(0) }.onSuccess { l -> unread = l?.let { a -> (0 until a.length()).count { !a.getJSONObject(it).optBoolean("leida") } } ?: 0 }
            loading = false
            delay(15_000)
        }
    }
    Column(Modifier.verticalScroll(rememberScrollState())) {
        ErrorText(err)
        if (unread > 0) ArcadeButton("🔔 $unread ALERTA${if (unread > 1) "S" else ""} SIN LEER", Modifier.fillMaxWidth(), color = Red) { openAlerts() }
        stats?.let { s ->
            PixelCard("INGRESOS") {
                for ((k, l) in listOf("today" to "HOY", "week" to "SEMANA", "total" to "TOTAL")) {
                    val o = s.getJSONObject(k)
                    Row { Text(l, Modifier.weight(1f)); Text(money(o.getDouble("income")), color = Orange) }
                    Spacer(Modifier.height(6.dp))
                }
            }
            PixelCard("CRÉDITOS") {
                Text("USADOS: ${s.optInt("credits_used")}")
                Text("EN COLA: ${s.optInt("credits_pending")}", style = MaterialTheme.typography.bodySmall)
                Text("PRECIO: ${money(s.optDouble("price"))}", color = LightOrange)
            }
        }
        status?.let { st ->
            PixelCard("ESTADO DEL EQUIPO") {
                Text("● PC ONLINE", color = Green)
                val tun = st.optString("tunnel_url").takeIf { !st.isNull("tunnel_url") && it.isNotBlank() }
                if (tun != null) Text("● TÚNEL OK", color = Green) else Text("● SIN TÚNEL: no puede cobrar", color = Red)
                if (!st.optBoolean("mp_configured")) Text("● FALTA CONFIGURAR MERCADO PAGO", color = Red)
                Text("ENCENDIDA HACE ${st.optLong("uptime_s") / 60} MIN", style = MaterialTheme.typography.bodySmall)
                Text("ÚLTIMO AVISO MP: ${st.optString("last_webhook", "-").replace("null", "-")}", style = MaterialTheme.typography.bodySmall)
            }
        }
        last?.let { p ->
            PixelCard("ÚLTIMO PAGO") {
                Text("${money(p.optDouble("amount"))} · ${statusEs(p.optString("status"))}")
                Text(p.optString("created_at").replace("T", " "), style = MaterialTheme.typography.bodySmall)
            }
        }
        Spacer(Modifier.height(8.dp))
        ArcadeButton(if (loading) "CARGANDO..." else "↻ REFRESCAR", Modifier.fillMaxWidth()) { tick++ }
        Spacer(Modifier.height(8.dp))
        ArcadeButton("🖨 IMPRIMIR QR", Modifier.fillMaxWidth(), color = LightOrange) {
            scope.launch {
                io { api.qrPng() }.onSuccess { bytes ->
                    val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    PrintHelper(ctx).apply { scaleMode = PrintHelper.SCALE_MODE_FIT }.printBitmap("QR Arcade", bmp)
                }.onFailure { err = it.message }
            }
        }
        Spacer(Modifier.height(8.dp))
        ArcadeButton("ABRIR PÁGINA IMPRIMIBLE", Modifier.fillMaxWidth(), color = Blue) {
            ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(api.printPageUrl())))
        }
        Spacer(Modifier.height(16.dp))
    }
}

fun statusEs(s: String) = when (s) {
    "approved" -> "APROBADO"; "pending", "in_process" -> "PENDIENTE"; "rejected" -> "RECHAZADO"
    "cancelled" -> "CANCELADO"; "refunded" -> "DEVUELTO"; else -> s.uppercase()
}

@Composable
fun History(api: Api) {
    var items by remember { mutableStateOf<JSONArray?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(api) {
        io { api.payments(200) }.onSuccess { items = it; err = null }.onFailure { err = it.message }
    }
    Column {
        Text("HISTORIAL", style = MaterialTheme.typography.titleMedium)
        ErrorText(err)
        val list = items
        if (list != null && list.length() == 0) Text("Todavía no hay pagos.")
        if (list != null) LazyColumn {
            items(list.length()) { i ->
                val p = list.getJSONObject(i)
                val st = p.optString("status")
                Column(Modifier.fillMaxWidth().padding(vertical = 4.dp).background(Blue).padding(10.dp)) {
                    Row {
                        Text(money(p.optDouble("amount")), Modifier.weight(1f), color = Orange)
                        Text(statusEs(st), color = when (st) { "approved" -> Green; "rejected", "cancelled" -> Red; else -> LightOrange },
                            style = MaterialTheme.typography.bodySmall)
                    }
                    Text(p.optString("created_at").replace("T", " "), style = MaterialTheme.typography.bodySmall)
                    val cr = when (p.optInt("credited")) { 1 -> "crédito cargado"; 2 -> "en cola"; else -> "sin cargar" }
                    Text("#${p.optString("payment_id")} · $cr", style = MaterialTheme.typography.bodySmall, color = Color.LightGray)
                }
            }
        }
    }
}

@Composable
fun PriceScreen(api: Api) {
    var current by remember { mutableStateOf<Double?>(null) }
    var input by remember { mutableStateOf("") }
    var msg by remember { mutableStateOf<String?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    var confirm by remember { mutableStateOf<Double?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(api) { io { api.stats().getDouble("price") }.onSuccess { current = it }.onFailure { err = it.message } }
    Column {
        PixelCard("PRECIO ACTUAL") { Text(current?.let { money(it) } ?: "...", style = MaterialTheme.typography.titleLarge) }
        OutlinedTextField(input, { input = it.filter(Char::isDigit) }, label = { Text("Nuevo precio ($)") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true,
            modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(10.dp))
        ArcadeButton("CAMBIAR PRECIO", Modifier.fillMaxWidth()) {
            val v = input.toDoubleOrNull()
            if (v == null || v <= 0) err = "Ingresá un precio mayor a 0" else confirm = v
        }
        ErrorText(err)
        msg?.let { Text("✔ $it", color = Green) }
    }
    confirm?.let { v ->
        AlertDialog(onDismissRequest = { confirm = null }, containerColor = DeepBlue,
            title = { Text("¿CONFIRMÁS?", style = MaterialTheme.typography.titleMedium) },
            text = { Text("El crédito va a pasar a costar ${money(v)}. Se aplica al instante.") },
            confirmButton = { TextButton({
                confirm = null
                scope.launch { io { api.setPrice(v) }.onSuccess { current = it; msg = "Precio actualizado"; err = null; input = "" }.onFailure { err = it.message } }
            }) { Text("SÍ", color = Orange) } },
            dismissButton = { TextButton({ confirm = null }) { Text("NO") } })
    }
}

@Composable
fun ConfigScreen(prefs: Prefs, onSaved: () -> Unit) {
    var host by remember { mutableStateOf(prefs.host) }
    var key by remember { mutableStateOf(prefs.key) }
    var result by remember { mutableStateOf<Pair<Boolean, String>?>(null) }
    val scope = rememberCoroutineScope()
    Column(Modifier.verticalScroll(rememberScrollState())) {
        Text("CONFIGURACIÓN", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        Text("IP y puerto de la PC del arcade (mismo WiFi):", style = MaterialTheme.typography.bodySmall)
        OutlinedTextField(host, { host = it.trim() }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("192.168.1.50:8000") })
        Spacer(Modifier.height(8.dp))
        Text("Clave de administrador (ADMIN_KEY del .env):", style = MaterialTheme.typography.bodySmall)
        OutlinedTextField(key, { key = it.trim() }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            visualTransformation = PasswordVisualTransformation())
        Spacer(Modifier.height(12.dp))
        ArcadeButton("PROBAR CONEXIÓN", Modifier.fillMaxWidth(), color = LightOrange) {
            result = null
            scope.launch {
                io { Api(host, key).status() }.onSuccess { result = true to "¡Conectado! La PC responde." }
                    .onFailure { result = false to (it.message ?: "Error") }
            }
        }
        Spacer(Modifier.height(8.dp))
        ArcadeButton("GUARDAR", Modifier.fillMaxWidth()) { prefs.host = host; prefs.key = key; onSaved() }
        result?.let { Text(it.second, color = if (it.first) Green else Red, modifier = Modifier.padding(top = 8.dp)) }
    }
}

@Composable
fun AlertsScreen(api: Api) {
    var items by remember { mutableStateOf<JSONArray?>(null) }
    var missing by remember { mutableStateOf(false) }
    var err by remember { mutableStateOf<String?>(null) }
    var tick by remember { mutableStateOf(0) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(api, tick) {
        io { api.alertas(0) }.onSuccess { if (it == null) missing = true else items = it; err = null }.onFailure { err = it.message }
    }
    Column {
        Text("ALERTAS", style = MaterialTheme.typography.titleMedium)
        ErrorText(err)
        if (missing) Text("El servidor todavía no tiene alertas. Actualizá el programa de la PC.", color = LightOrange)
        ArcadeButton("MARCAR TODAS LEÍDAS", Modifier.fillMaxWidth(), color = LightOrange) {
            scope.launch { io { api.marcarLeidas() }.onFailure { err = it.message }; tick++ }
        }
        val list = items
        if (list != null && list.length() == 0) Text("Sin alertas. ¡Todo en orden!", color = Green)
        if (list != null) LazyColumn {
            items(list.length()) { i ->
                val a = list.getJSONObject(list.length() - 1 - i)   // más nuevas arriba
                val c = when (a.optString("nivel")) { "error" -> Red; "warning" -> Orange; else -> Color(0xFF4FC3F7) }
                Column(Modifier.fillMaxWidth().padding(vertical = 4.dp).border(3.dp, c).background(Blue).padding(10.dp)) {
                    Row {
                        Text(a.optString("nivel").uppercase() + " · " + a.optString("tipo"), Modifier.weight(1f), color = c,
                            style = MaterialTheme.typography.bodySmall)
                        if (!a.optBoolean("leida")) Text("NUEVA", color = LightOrange, style = MaterialTheme.typography.bodySmall)
                    }
                    Text(a.optString("mensaje"))
                    Text(a.optString("fecha").replace("T", " "), style = MaterialTheme.typography.bodySmall, color = Color.LightGray)
                }
            }
        }
    }
}

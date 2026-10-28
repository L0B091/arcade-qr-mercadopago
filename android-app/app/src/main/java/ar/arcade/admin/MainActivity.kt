package ar.arcade.admin

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.print.PrintHelper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.text.NumberFormat
import java.time.LocalDate
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

enum class Tab(val label: String, val icon: ImageVector) {
    DASH("Inicio", Icons.Filled.Home), HIST("Pagos", Icons.Filled.List), PRICE("Precio", Icons.Filled.Edit),
    ALERT("Alertas", Icons.Filled.Notifications), CONF("Config", Icons.Filled.Settings)
}

fun money(v: Double): String = "$" + NumberFormat.getIntegerInstance(Locale("es", "AR")).format(v.toLong())
fun fecha(s: String) = s.replace("T", " ").take(16)

suspend fun <T> io(block: () -> T): Result<T> = withContext(Dispatchers.IO) { runCatching(block) }

@Composable
fun App(prefs: Prefs, start: Tab? = null) {
    var tab by remember { mutableStateOf(start ?: if (prefs.configured) Tab.DASH else Tab.CONF) }
    var api by remember { mutableStateOf(Api(prefs.host, prefs.key)) }
    var unread by remember { mutableStateOf(0) }
    val ctx = LocalContext.current
    LaunchedEffect(Unit) { while (true) { io { Vigilante.check(ctx) }; delay(60_000) } }  // chequeo rápido con la app abierta
    LaunchedEffect(api) {
        while (true) {
            io { api.alertas(0) }.onSuccess { l -> unread = l?.let { a -> (0 until a.length()).count { !a.getJSONObject(it).optBoolean("leida") } } ?: 0 }
            delay(20_000)
        }
    }
    Scaffold(containerColor = Color.Transparent, modifier = Modifier.appBackground(),
        bottomBar = {
            NavigationBar(containerColor = Color(0xF20D1426), tonalElevation = 0.dp) {
                Tab.values().forEach { t ->
                    NavigationBarItem(selected = t == tab, onClick = { tab = t },
                        icon = {
                            if (t == Tab.ALERT && unread > 0) BadgedBox(badge = { Badge(containerColor = Orange) { Text("$unread") } }) { Icon(t.icon, t.label) }
                            else Icon(t.icon, t.label)
                        },
                        label = { Text(t.label, style = MaterialTheme.typography.labelSmall) },
                        colors = NavigationBarItemDefaults.colors(selectedIconColor = Color.White, selectedTextColor = Cyan,
                            indicatorColor = Blue.copy(alpha = 0.35f), unselectedIconColor = Muted, unselectedTextColor = Muted))
                }
            }
        }) { pad ->
        Column(Modifier.fillMaxSize().padding(pad).padding(horizontal = 16.dp)) {
            Header(tab)
            when (tab) {
                Tab.DASH -> Dashboard(api, unread) { tab = Tab.ALERT }
                Tab.HIST -> History(api)
                Tab.PRICE -> PriceScreen(api)
                Tab.ALERT -> AlertsScreen(api) { unread = 0 }
                Tab.CONF -> ConfigScreen(prefs) { api = Api(prefs.host, prefs.key); tab = Tab.DASH }
            }
        }
    }
}

@Composable
fun Header(tab: Tab) {
    Row(Modifier.fillMaxWidth().padding(top = 18.dp, bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(40.dp).clip(RoundedCornerShape(12.dp)).background(Brush.linearGradient(listOf(Blue, Cyan))),
            contentAlignment = Alignment.Center) { Icon(Icons.Filled.PlayArrow, null, tint = Color.White) }
        Spacer(Modifier.width(12.dp))
        Column {
            Text("ARCADE ADMIN", style = MaterialTheme.typography.titleLarge)
            Text(tab.label, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun ErrorBanner(e: String?) {
    if (e != null) Row(Modifier.fillMaxWidth().padding(vertical = 6.dp).clip(RoundedCornerShape(14.dp))
        .background(Red.copy(alpha = 0.12f)).border(1.dp, Red.copy(alpha = 0.4f), RoundedCornerShape(14.dp)).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Filled.Warning, null, tint = Red, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(8.dp))
        Text(e, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
fun StatusDot(ok: Boolean, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 3.dp)) {
        Box(Modifier.size(9.dp).clip(CircleShape).background(if (ok) Green else Red))
        Spacer(Modifier.width(10.dp)); Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}

/** Ingresos aprobados de los últimos 7 días (para el gráfico). */
fun last7(items: JSONArray?): Pair<List<Double>, List<String>> {
    val today = LocalDate.now()
    val days = (6 downTo 0).map { today.minusDays(it.toLong()) }
    val sums = DoubleArray(7)
    if (items != null) for (i in 0 until items.length()) {
        val p = items.getJSONObject(i)
        if (p.optString("status") != "approved") continue
        val d = runCatching { LocalDate.parse(p.optString("created_at").take(10)) }.getOrNull() ?: continue
        val idx = days.indexOf(d); if (idx >= 0) sums[idx] += p.optDouble("amount")
    }
    val names = listOf("L", "M", "X", "J", "V", "S", "D")
    return sums.toList() to days.map { names[it.dayOfWeek.value - 1] }
}

@Composable
fun Dashboard(api: Api, unread: Int, openAlerts: () -> Unit) {
    var stats by remember { mutableStateOf<JSONObject?>(null) }
    var status by remember { mutableStateOf<JSONObject?>(null) }
    var pays by remember { mutableStateOf<JSONArray?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    var tick by remember { mutableStateOf(0) }
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    LaunchedEffect(api, tick) {
        while (true) {   // auto-refresh cada 15 s
            loading = true
            io { Triple(api.stats(), api.status(), api.payments(500)) }
                .onSuccess { stats = it.first; status = it.second; pays = it.third; err = null }
                .onFailure { err = it.message }
            loading = false
            delay(15_000)
        }
    }
    Column(Modifier.verticalScroll(rememberScrollState())) {
        ErrorBanner(err)
        if (unread > 0) GlassCard(glow = Orange, modifier = Modifier) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Notifications, null, tint = Orange); Spacer(Modifier.width(10.dp))
                Text("$unread alerta${if (unread > 1) "s" else ""} sin leer", Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                TextButton(openAlerts) { Text("VER", color = Orange, style = MaterialTheme.typography.labelLarge) }
            }
        }
        val s = stats
        GlassCard(glow = Cyan) {
            SectionTitle("Ingresos de hoy", Icons.Filled.Star)
            AnimatedNumber(s?.getJSONObject("today")?.optDouble("income") ?: 0.0, ::money, MaterialTheme.typography.displaySmall)
            Text("${s?.getJSONObject("today")?.optInt("credits") ?: 0} créditos hoy", style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(14.dp))
            val (v, l) = last7(pays)
            BarChart(v, l)
        }
        Row {
            GlassCard(Modifier.weight(1f).padding(end = 6.dp)) {
                SectionTitle("Semana")
                AnimatedNumber(s?.getJSONObject("week")?.optDouble("income") ?: 0.0, ::money, MaterialTheme.typography.headlineSmall)
            }
            GlassCard(Modifier.weight(1f).padding(start = 6.dp), glow = Orange) {
                SectionTitle("Total", tint = Orange)
                AnimatedNumber(s?.getJSONObject("total")?.optDouble("income") ?: 0.0, ::money, MaterialTheme.typography.headlineSmall, Orange)
            }
        }
        Row {
            GlassCard(Modifier.weight(1f).padding(end = 6.dp)) {
                SectionTitle("Créditos")
                AnimatedNumber((s?.optInt("credits_used") ?: 0).toDouble(), { it.toLong().toString() }, MaterialTheme.typography.headlineSmall)
                Text("${s?.optInt("credits_pending") ?: 0} en cola", style = MaterialTheme.typography.bodySmall)
            }
            GlassCard(Modifier.weight(1f).padding(start = 6.dp)) {
                SectionTitle("Precio")
                Text(s?.let { money(it.optDouble("price")) } ?: "—", style = MaterialTheme.typography.headlineSmall, color = Cyan)
                Text("por crédito", style = MaterialTheme.typography.bodySmall)
            }
        }
        GlassCard {
            SectionTitle("Estado del equipo", Icons.Filled.Build)
            Spacer(Modifier.height(6.dp))
            val st = status
            StatusDot(st != null, if (st != null) "PC online · ${st.optLong("uptime_s") / 60} min encendida" else "PC sin respuesta")
            val tun = st?.takeIf { !it.isNull("tunnel_url") }?.optString("tunnel_url")?.takeIf { it.isNotBlank() }
            StatusDot(tun != null, if (tun != null) "Túnel activo · puede cobrar" else "Sin túnel · no puede cobrar")
            StatusDot(st?.optBoolean("mp_configured") == true, "Mercado Pago configurado")
            Text("Último aviso MP: ${st?.takeIf { !it.isNull("last_webhook") }?.optString("last_webhook")?.let(::fecha) ?: "—"}",
                style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 4.dp))
        }
        pays?.optJSONObject(0)?.let { p ->
            GlassCard {
                SectionTitle("Último pago", Icons.Filled.CheckCircle)
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
                    Column(Modifier.weight(1f)) {
                        Text(money(p.optDouble("amount")), style = MaterialTheme.typography.headlineSmall)
                        Text(fecha(p.optString("created_at")), style = MaterialTheme.typography.bodySmall)
                    }
                    StatusChip(p.optString("status"))
                }
            }
        }
        Spacer(Modifier.height(6.dp))
        GradientButton("IMPRIMIR QR", icon = Icons.Filled.Share, accent = true) {
            scope.launch {
                io { api.qrPng() }.onSuccess { bytes ->
                    val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    PrintHelper(ctx).apply { scaleMode = PrintHelper.SCALE_MODE_FIT }.printBitmap("QR Arcade", bmp)
                }.onFailure { err = it.message }
            }
        }
        GhostButton("ABRIR PÁGINA IMPRIMIBLE", icon = Icons.Filled.Info) {
            ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(api.printPageUrl())))
        }
        GhostButton(if (loading) "ACTUALIZANDO…" else "ACTUALIZAR", icon = Icons.Filled.Refresh) { tick++ }
        Spacer(Modifier.height(16.dp))
    }
}

fun statusEs(s: String) = when (s) {
    "approved" -> "Aprobado"; "pending", "in_process" -> "Pendiente"; "rejected" -> "Rechazado"
    "cancelled" -> "Cancelado"; "refunded" -> "Devuelto"; else -> s
}

@Composable
fun StatusChip(st: String) = Chip(statusEs(st), when (st) { "approved" -> Green; "rejected", "cancelled" -> Red; else -> Orange })

@Composable
fun History(api: Api) {
    var items by remember { mutableStateOf<JSONArray?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(api) { io { api.payments(200) }.onSuccess { items = it; err = null }.onFailure { err = it.message } }
    Column {
        ErrorBanner(err)
        val list = items
        if (list != null && list.length() == 0) Text("Todavía no hay pagos.", style = MaterialTheme.typography.bodyLarge)
        if (list != null) LazyColumn {
            items(list.length()) { i ->
                val p = list.getJSONObject(i)
                GlassCard(glow = if (p.optString("status") == "approved") Blue else Orange) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(money(p.optDouble("amount")), style = MaterialTheme.typography.titleLarge)
                            Text(fecha(p.optString("created_at")), style = MaterialTheme.typography.bodySmall)
                        }
                        StatusChip(p.optString("status"))
                    }
                    val cr = when (p.optInt("credited")) { 1 -> "Crédito cargado"; 2 -> "En cola"; else -> "Sin cargar" }
                    Text("#${p.optString("payment_id")} · $cr", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp))
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
        GlassCard(glow = Orange) {
            SectionTitle("Precio actual por crédito", tint = Orange)
            AnimatedNumber(current ?: 0.0, ::money, MaterialTheme.typography.displaySmall, Orange)
        }
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(input, { input = it.filter(Char::isDigit) }, label = { Text("Nuevo precio ($)") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true,
            shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(10.dp))
        GradientButton("CAMBIAR PRECIO", icon = Icons.Filled.Check) {
            val v = input.toDoubleOrNull()
            if (v == null || v <= 0) err = "Ingresá un precio mayor a 0" else confirm = v
        }
        ErrorBanner(err)
        msg?.let { Text("✓ $it", color = Green, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(top = 8.dp)) }
    }
    confirm?.let { v ->
        AlertDialog(onDismissRequest = { confirm = null }, containerColor = Surface, shape = RoundedCornerShape(20.dp),
            title = { Text("¿Confirmás el cambio?", style = MaterialTheme.typography.titleLarge) },
            text = { Text("El crédito va a pasar a costar ${money(v)}. Se aplica al instante.", style = MaterialTheme.typography.bodyLarge) },
            confirmButton = { TextButton({
                confirm = null
                scope.launch { io { api.setPrice(v) }.onSuccess { current = it; msg = "Precio actualizado"; err = null; input = "" }.onFailure { err = it.message } }
            }) { Text("CONFIRMAR", color = Orange, style = MaterialTheme.typography.labelLarge) } },
            dismissButton = { TextButton({ confirm = null }) { Text("CANCELAR", color = Muted, style = MaterialTheme.typography.labelLarge) } })
    }
}

@Composable
fun ConfigScreen(prefs: Prefs, onSaved: () -> Unit) {
    var host by remember { mutableStateOf(prefs.host) }
    var key by remember { mutableStateOf(prefs.key) }
    var result by remember { mutableStateOf<Pair<Boolean, String>?>(null) }
    val scope = rememberCoroutineScope()
    Column(Modifier.verticalScroll(rememberScrollState())) {
        GlassCard {
            SectionTitle("Conexión con la PC", Icons.Filled.Settings)
            Text("Conectá el celular al mismo WiFi que el arcade.", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 6.dp))
            OutlinedTextField(host, { host = it.trim() }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                label = { Text("IP:puerto de la PC") }, placeholder = { Text("192.168.1.50:8000") }, shape = RoundedCornerShape(16.dp))
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(key, { key = it.trim() }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                label = { Text("Clave de administrador") }, leadingIcon = { Icon(Icons.Filled.Lock, null) },
                visualTransformation = PasswordVisualTransformation(), shape = RoundedCornerShape(16.dp))
        }
        Spacer(Modifier.height(6.dp))
        GhostButton("PROBAR CONEXIÓN", icon = Icons.Filled.Refresh) {
            result = null
            scope.launch {
                io { Api(host, key).status() }.onSuccess { result = true to "¡Conectado! La PC responde." }
                    .onFailure { result = false to (it.message ?: "Error") }
            }
        }
        GradientButton("GUARDAR", icon = Icons.Filled.Check) { prefs.host = host; prefs.key = key; onSaved() }
        result?.let { if (it.first) Text(it.second, color = Green, modifier = Modifier.padding(top = 8.dp)) else ErrorBanner(it.second) }
    }
}

@Composable
fun AlertsScreen(api: Api, onRead: () -> Unit) {
    var items by remember { mutableStateOf<JSONArray?>(null) }
    var missing by remember { mutableStateOf(false) }
    var err by remember { mutableStateOf<String?>(null) }
    var tick by remember { mutableStateOf(0) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(api, tick) {
        io { api.alertas(0) }.onSuccess { if (it == null) missing = true else items = it; err = null }.onFailure { err = it.message }
    }
    Column {
        ErrorBanner(err)
        if (missing) Text("El servidor todavía no tiene alertas. Actualizá el programa de la PC.", color = Orange, style = MaterialTheme.typography.bodyMedium)
        GhostButton("MARCAR TODAS COMO LEÍDAS", icon = Icons.Filled.Done) {
            scope.launch { io { api.marcarLeidas() }.onSuccess { onRead() }.onFailure { err = it.message }; tick++ }
        }
        val list = items
        if (list != null && list.length() == 0) GlassCard(glow = Green) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.CheckCircle, null, tint = Green); Spacer(Modifier.width(10.dp))
                Text("Sin alertas. Todo en orden.", style = MaterialTheme.typography.bodyLarge)
            }
        }
        if (list != null) LazyColumn {
            items(list.length()) { i ->
                AlertCard(list.getJSONObject(list.length() - 1 - i))   // más nuevas arriba
            }
        }
    }
}

@Composable
fun AlertCard(a: JSONObject) {
    val nivel = a.optString("nivel")
    val c = when (nivel) { "error" -> Red; "warning" -> Orange; else -> Cyan }
    val icon = when (nivel) { "error" -> Icons.Filled.Warning; "warning" -> Icons.Filled.Warning; else -> Icons.Filled.Info }
    GlassCard(glow = c) {
        Row(verticalAlignment = Alignment.Top) {
            Box(Modifier.size(36.dp).clip(RoundedCornerShape(12.dp)).background(c.copy(alpha = 0.15f)), contentAlignment = Alignment.Center) {
                Icon(icon, null, tint = c, modifier = Modifier.size(20.dp))
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(a.optString("tipo").replace('_', ' ').uppercase(), Modifier.weight(1f), style = MaterialTheme.typography.labelLarge, color = c)
                    if (!a.optBoolean("leida")) Chip("NUEVA", Orange)
                }
                Text(a.optString("mensaje"), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(vertical = 4.dp))
                Text(fecha(a.optString("fecha")), style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

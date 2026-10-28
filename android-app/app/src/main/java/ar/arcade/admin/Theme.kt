package ar.arcade.admin

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// Paleta "esports dashboard": fondo oscuro, azul eléctrico y naranja de acento.
val Bg = Color(0xFF0A0F1F)
val Surface = Color(0xFF111827)
val SurfaceHi = Color(0xFF1A2236)
val Blue = Color(0xFF2F6BFF)
val Cyan = Color(0xFF00B4FF)
val Orange = Color(0xFFFF7A00)
val Muted = Color(0xFF8B95A7)
val Green = Color(0xFF22E39B)
val Red = Color(0xFFFF4D5E)

val Heading = FontFamily(Font(R.font.rajdhani_semibold, FontWeight.SemiBold), Font(R.font.rajdhani_bold, FontWeight.Bold))
val Body = FontFamily(Font(R.font.inter))

@Composable
fun ArcadeTheme(content: @Composable () -> Unit) {
    val b = TextStyle(fontFamily = Body, color = Color.White)
    val h = TextStyle(fontFamily = Heading, fontWeight = FontWeight.Bold, color = Color.White)
    MaterialTheme(
        colorScheme = darkColorScheme(primary = Blue, secondary = Orange, tertiary = Cyan, background = Bg,
            surface = Surface, surfaceVariant = SurfaceHi, onPrimary = Color.White, onBackground = Color.White,
            onSurface = Color.White, onSurfaceVariant = Muted, outline = Color(0xFF2A3550)),
        typography = Typography(
            displaySmall = h.copy(fontSize = 34.sp),
            headlineSmall = h.copy(fontSize = 26.sp),
            titleLarge = h.copy(fontSize = 22.sp, letterSpacing = 1.sp),
            titleMedium = h.copy(fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = Muted, letterSpacing = 1.5.sp),
            bodyLarge = b.copy(fontSize = 15.sp), bodyMedium = b.copy(fontSize = 13.sp),
            bodySmall = b.copy(fontSize = 11.sp, color = Muted),
            labelLarge = h.copy(fontSize = 15.sp, letterSpacing = 1.sp),
            labelSmall = b.copy(fontSize = 10.sp),
        ), content = content)
}

val CardShape = RoundedCornerShape(18.dp)

/** Fondo con degradé suave y halos de color. */
fun Modifier.appBackground() = background(Bg).drawBehind {
    drawCircle(Brush.radialGradient(listOf(Blue.copy(alpha = 0.22f), Color.Transparent), Offset(size.width * 0.1f, 0f), size.width * 0.8f))
    drawCircle(Brush.radialGradient(listOf(Orange.copy(alpha = 0.10f), Color.Transparent), Offset(size.width, size.height * 0.55f), size.width * 0.7f))
}

/** Card tipo "glass" con borde neón suave y glow exterior. */
@Composable
fun GlassCard(modifier: Modifier = Modifier, glow: Color = Blue, content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.fillMaxWidth().padding(vertical = 6.dp)
        .drawBehind {
            for (i in 1..3) drawRoundRect(glow.copy(alpha = 0.07f / i), Offset(-i * 3f, -i * 3f),
                size.copy(size.width + i * 6f, size.height + i * 6f), CornerRadius(22.dp.toPx() + i * 3f), style = Stroke(6f))
        }
        .clip(CardShape)
        .background(Brush.verticalGradient(listOf(SurfaceHi.copy(alpha = 0.92f), Surface.copy(alpha = 0.85f))))
        .border(1.dp, Brush.linearGradient(listOf(glow.copy(alpha = 0.7f), glow.copy(alpha = 0.08f))), CardShape)
        .padding(16.dp), content = content)
}

@Composable
fun SectionTitle(text: String, icon: ImageVector? = null, tint: Color = Cyan) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        if (icon != null) { Icon(icon, null, tint = tint, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)) }
        Text(text.uppercase(), style = MaterialTheme.typography.titleMedium)
    }
}

/** Botón principal con degradé azul→cian (o naranja). */
@Composable
fun GradientButton(text: String, modifier: Modifier = Modifier, icon: ImageVector? = null, accent: Boolean = false,
                   enabled: Boolean = true, onClick: () -> Unit) {
    val colors = if (accent) listOf(Orange, Color(0xFFFFA94D)) else listOf(Blue, Cyan)
    Box(modifier.fillMaxWidth().padding(vertical = 4.dp).clip(RoundedCornerShape(16.dp))
        .background(Brush.horizontalGradient(colors.map { if (enabled) it else it.copy(alpha = 0.4f) }))
        .clickable(enabled = enabled, onClick = onClick).padding(vertical = 14.dp), contentAlignment = Alignment.Center) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (icon != null) { Icon(icon, null, tint = Color.White, modifier = Modifier.size(20.dp)); Spacer(Modifier.width(8.dp)) }
            Text(text, style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
fun GhostButton(text: String, modifier: Modifier = Modifier, icon: ImageVector? = null, onClick: () -> Unit) {
    OutlinedButton(onClick, modifier.fillMaxWidth().padding(vertical = 4.dp), shape = RoundedCornerShape(16.dp),
        border = BorderStroke(1.dp, Cyan.copy(alpha = 0.5f)), contentPadding = PaddingValues(vertical = 13.dp)) {
        if (icon != null) { Icon(icon, null, tint = Cyan, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)) }
        Text(text, style = MaterialTheme.typography.labelLarge.copy(color = Cyan))
    }
}

/** Número que sube animado hasta el valor. */
@Composable
fun AnimatedNumber(value: Double, format: (Double) -> String, style: TextStyle, color: Color = Color.White) {
    var target by remember { mutableStateOf(0.0) }
    LaunchedEffect(value) { target = value }
    val v by animateFloatAsState(target.toFloat(), tween(900), label = "n")
    Text(format(v.toDouble()), style = style, color = color)
}

@Composable
fun Chip(text: String, color: Color) {
    Text(text, style = MaterialTheme.typography.labelSmall.copy(color = color, fontWeight = FontWeight.SemiBold),
        modifier = Modifier.clip(RoundedCornerShape(50)).background(color.copy(alpha = 0.15f))
            .border(1.dp, color.copy(alpha = 0.4f), RoundedCornerShape(50)).padding(horizontal = 10.dp, vertical = 4.dp))
}

/** Gráfico de barras simple (Canvas) con degradé azul y la barra de hoy en naranja. */
@Composable
fun BarChart(values: List<Double>, labels: List<String>, height: Dp = 120.dp) {
    val max = (values.maxOrNull() ?: 0.0).coerceAtLeast(1.0)
    val anim by animateFloatAsState(1f, tween(900), label = "c")
    Column {
        Canvas(Modifier.fillMaxWidth().height(height)) {
            val n = values.size.coerceAtLeast(1)
            val slot = size.width / n
            val bw = slot * 0.55f
            for (i in 0..3) drawLine(Color.White.copy(alpha = 0.05f), Offset(0f, size.height * i / 3), Offset(size.width, size.height * i / 3), 1f)
            values.forEachIndexed { i, v ->
                val h = (v / max).toFloat() * size.height * anim
                val last = i == values.lastIndex
                drawRoundRect(Brush.verticalGradient(if (last) listOf(Color(0xFFFFA94D), Orange) else listOf(Cyan, Blue),
                    startY = size.height - h, endY = size.height),
                    Offset(slot * i + (slot - bw) / 2, size.height - h.coerceAtLeast(3f)),
                    androidx.compose.ui.geometry.Size(bw, h.coerceAtLeast(3f)), CornerRadius(8f))
            }
        }
        Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
            labels.forEach { Text(it, Modifier.weight(1f), style = MaterialTheme.typography.labelSmall.copy(color = Muted),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center) }
        }
    }
}

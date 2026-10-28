package ar.arcade.admin

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val DeepBlue = Color(0xFF0B1A3A)
val Blue = Color(0xFF1E3A8A)
val Orange = Color(0xFFFF7A00)
val LightOrange = Color(0xFFFFA94D)
val Green = Color(0xFF39FF14)
val Red = Color(0xFFFF3B3B)

val Pixel = FontFamily(Font(R.font.press_start_2p))

@Composable
fun ArcadeTheme(content: @Composable () -> Unit) {
    val t = TextStyle(fontFamily = Pixel, color = Color.White)
    MaterialTheme(
        colorScheme = darkColorScheme(primary = Orange, secondary = LightOrange, background = DeepBlue,
            surface = Blue, onPrimary = DeepBlue, onBackground = Color.White, onSurface = Color.White),
        typography = Typography(
            bodyLarge = t.copy(fontSize = 12.sp, lineHeight = 18.sp),
            bodyMedium = t.copy(fontSize = 10.sp, lineHeight = 16.sp),
            bodySmall = t.copy(fontSize = 8.sp, lineHeight = 12.sp),
            titleLarge = t.copy(fontSize = 18.sp, color = Orange),
            titleMedium = t.copy(fontSize = 12.sp, color = LightOrange),
            labelLarge = t.copy(fontSize = 11.sp),
        ), content = content)
}

/** Líneas horizontales tipo monitor CRT encima del contenido. */
fun Modifier.scanlines() = drawWithContent {
    drawContent()
    var y = 0f
    while (y < size.height) { drawLine(Color.Black.copy(alpha = 0.18f), Offset(0f, y), Offset(size.width, y), 1f); y += 4f }
}

/** Botón arcade: naranja, borde grueso y "sombra" pixelada. */
@Composable
fun ArcadeButton(text: String, modifier: Modifier = Modifier, color: Color = Orange, enabled: Boolean = true, onClick: () -> Unit) {
    Box(modifier.padding(bottom = 4.dp, end = 4.dp)) {
        Box(Modifier.matchParentSize().offset(4.dp, 4.dp).background(Color.Black))
        Button(onClick = onClick, enabled = enabled, shape = RoundedCornerShape(2.dp),
            colors = ButtonDefaults.buttonColors(containerColor = color, contentColor = DeepBlue),
            border = BorderStroke(3.dp, LightOrange), modifier = Modifier.fillMaxWidth()) {
            Text(text, style = MaterialTheme.typography.labelLarge.copy(color = DeepBlue))
        }
    }
}

@Composable
fun PixelCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth().padding(vertical = 6.dp).border(3.dp, Orange).background(Blue).padding(12.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        content()
    }
}

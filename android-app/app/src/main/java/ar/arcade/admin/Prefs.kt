package ar.arcade.admin

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** Guarda IP:puerto y clave admin cifradas en el teléfono. */
class Prefs(ctx: Context) {
    private val sp: SharedPreferences = try {
        EncryptedSharedPreferences.create(ctx, "arcade_admin",
            MasterKey.Builder(ctx).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)
    } catch (e: Exception) { ctx.getSharedPreferences("arcade_admin_plain", Context.MODE_PRIVATE) }

    var host: String get() = sp.getString("host", "192.168.1.50:8000")!!; set(v) = sp.edit().putString("host", v).apply()
    var key: String get() = sp.getString("key", "")!!; set(v) = sp.edit().putString("key", v).apply()
    var lastAlertId: Long get() = sp.getLong("last_alert_id", 0); set(v) = sp.edit().putLong("last_alert_id", v).apply()
    var failCount: Int get() = sp.getInt("fail_count", 0); set(v) = sp.edit().putInt("fail_count", v).apply()
    var offlineNotified: Boolean get() = sp.getBoolean("offline_notified", false); set(v) = sp.edit().putBoolean("offline_notified", v).apply()
    val configured get() = key.isNotBlank()
}

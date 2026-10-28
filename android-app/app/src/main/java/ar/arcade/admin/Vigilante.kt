package ar.arcade.admin

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.*
import java.util.concurrent.TimeUnit

/**
 * "Vigilante": revisa alertas nuevas (warning/error) y si la PC dejó de responder.
 * Corre cada 15 min con WorkManager (mínimo de Android) y también desde la app abierta.
 */
object Vigilante {
    const val CHANNEL = "vigilante"
    private const val OFFLINE_ID = 1

    fun schedule(ctx: Context) {
        val req = PeriodicWorkRequestBuilder<Worker>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build()
        WorkManager.getInstance(ctx).enqueueUniquePeriodicWork("vigilante", ExistingPeriodicWorkPolicy.KEEP, req)
    }

    fun createChannel(ctx: Context) {
        if (Build.VERSION.SDK_INT >= 26)
            ctx.getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(CHANNEL, "Vigilante", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "Alertas del arcade y PC sin conexión" })
    }

    /** Un chequeo completo. Seguro de llamar desde cualquier hilo de fondo. */
    fun check(ctx: Context) {
        val p = Prefs(ctx)
        if (!p.configured) return
        val api = Api(p.host, p.key)
        try {
            val list = api.alertas(p.lastAlertId)
            p.failCount = 0
            if (p.offlineNotified) { p.offlineNotified = false; NotificationManagerCompat.from(ctx).cancel(OFFLINE_ID) }
            if (list != null) {
                var maxId = p.lastAlertId
                for (i in 0 until list.length()) {
                    val a = list.getJSONObject(i)
                    val id = a.optLong("id")
                    if (id <= p.lastAlertId) continue
                    if (id > maxId) maxId = id
                    val nivel = a.optString("nivel")
                    if (nivel == "warning" || nivel == "error")
                        notify(ctx, (1000 + id % 100000).toInt(),
                            (if (nivel == "error") "⚠ ERROR" else "⚠ Aviso") + " · " + a.optString("tipo"), a.optString("mensaje"))
                }
                p.lastAlertId = maxId
            }
        } catch (e: ApiException) {
            if (e.code != 0) return          // 401/403: no es "PC caída"
            offline(ctx, p)
        } catch (e: Exception) { offline(ctx, p) }
    }

    private fun offline(ctx: Context, p: Prefs) {
        p.failCount = p.failCount + 1
        if (p.failCount >= 2 && !p.offlineNotified) {
            notify(ctx, OFFLINE_ID, "PC del arcade sin respuesta", "No responde en el WiFi del local (2 chequeos seguidos). ¿Está prendida?")
            p.offlineNotified = true
        }
    }

    private fun notify(ctx: Context, id: Int, title: String, text: String) {
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED) return
        createChannel(ctx)
        val pi = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java).putExtra("tab", "ALERTAS"),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        NotificationManagerCompat.from(ctx).notify(id, NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_notify_error).setContentTitle(title).setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text)).setContentIntent(pi).setAutoCancel(true).build())
    }

    class Worker(ctx: Context, params: WorkerParameters) : androidx.work.Worker(ctx, params) {
        override fun doWork(): Result { check(applicationContext); return Result.success() }
    }
}

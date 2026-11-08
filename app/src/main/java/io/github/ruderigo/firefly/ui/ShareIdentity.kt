package io.github.ruderigo.firefly.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import io.github.ruderigo.firefly.R
import io.github.ruderigo.firefly.engine.Engine

/**
 * Settings › Identity › Share (Nov 2026): FireFly's own address as a QR code, in the format each
 * family of LXMF apps reads:
 *  - Sideband / NomadNet (the default): the bare 32-character address (Sideband, NomadNet,
 *    Skywave, any LXMF app that takes an address);
 *  - Columba / MeshChatX: lxma://<address>:<public key> (also the T-Deck messenger, FireFly and
 *    Stumps): with the key they can write at once, before FireFly's announce;
 *  - Link: lxmf://<address>, which opens an LXMF app when tapped.
 * Under it: the address as text (NomadNet can't scan: it's typed), Copy, and Android's Share.
 */
@Composable
fun ShareIdentityPopup(onDismiss: () -> Unit) {
    val ctx = LocalContext.current
    val codes = engineData(org.json.JSONObject()) { Engine.obj("share_codes") }
    val choices = buildList {
        add(Triple("bare", R.string.share_fmt_sideband, R.string.share_for_sideband))
        if (!codes.isNull("lxma") && codes.optString("lxma").isNotBlank()) add(Triple("lxma", R.string.share_fmt_columba, R.string.share_for_columba))
        add(Triple("link", R.string.share_fmt_link, R.string.share_for_link))
    }
    var which by remember { mutableStateOf("bare") }
    val text = codes.optString(which).takeIf { it.isNotBlank() && it != "null" }
    val qr = remember(text) { text?.let { qrBitmap(it, 720) } }
    val address = codes.optString("address")

    androidx.compose.material3.AlertDialog(
        onDismissRequest = onDismiss, containerColor = Amber.Panel, shape = Large,
        title = { Text(stringResource(R.string.share_title), style = MaterialTheme.typography.titleMedium) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), horizontalAlignment = Alignment.CenterHorizontally) {
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState())) {
                    choices.forEach { (k, label, _) -> Chip(stringResource(label), which == k) { which = k } }
                }
                Spacer(Modifier.height(12.dp))
                // Dark on white, with a quiet zone: what every camera app reads best.
                Box(Modifier.size(240.dp).clip(Medium).background(androidx.compose.ui.graphics.Color.White).padding(10.dp),
                    contentAlignment = Alignment.Center) {
                    if (qr != null) Image(qr.asImageBitmap(), contentDescription = text, modifier = Modifier.fillMaxSize())
                }
                Spacer(Modifier.height(8.dp))
                Text(stringResource(choices.firstOrNull { it.first == which }?.third ?: R.string.share_for_sideband),
                    style = MaterialTheme.typography.labelMedium)
                Spacer(Modifier.height(10.dp))
                // The address to read out or type, in groups of four.
                Text(address.chunked(4).joinToString(" "), style = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace))
                Spacer(Modifier.height(10.dp))
                Row {
                    Button(stringResource(R.string.share_copy), primary = false) {
                        val t = text ?: return@Button
                        ctx.getSystemService(ClipboardManager::class.java)?.setPrimaryClip(ClipData.newPlainText("LXMF", t))
                        Toast.makeText(ctx, ctx.getString(R.string.share_copied), Toast.LENGTH_SHORT).show()
                    }
                    Spacer(Modifier.width(8.dp))
                    Button(stringResource(R.string.share_send)) {
                        val t = text ?: return@Button
                        val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, t)
                        ctx.startActivity(Intent.createChooser(send, ctx.getString(R.string.share_title))
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    }
                }
            }
        },
        confirmButton = {
            Text(stringResource(R.string.close), modifier = Modifier.clip(Small).clickable { onDismiss() }.padding(10.dp),
                style = MaterialTheme.typography.labelLarge.copy(color = Amber.Ember))
        })
}

/** A QR code as a bitmap: black on white, error correction M, a 2-module quiet zone. */
private fun qrBitmap(text: String, size: Int): Bitmap? = runCatching {
    val m = QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, size, size,
        mapOf(EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M, EncodeHintType.MARGIN to 2,
            EncodeHintType.CHARACTER_SET to "UTF-8"))
    val px = IntArray(m.width * m.height) { i -> if (m.get(i % m.width, i / m.width)) Color.BLACK else Color.WHITE }
    Bitmap.createBitmap(px, m.width, m.height, Bitmap.Config.RGB_565)
}.getOrNull()

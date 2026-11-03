package io.github.ruderigo.firefly.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.res.stringResource
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import io.github.ruderigo.firefly.R

/**
 * The camera, for a QR code: a Stump's address (its home page › Its address, Stump
 * 1.0.0-beta.51) or anyone's LXMF address. ZXing's scanner: offline, no Google services.
 * It asks for the camera itself the first time; refused or cancelled, [onResult] gets null
 * and typing the address still works. Returns what starts a scan.
 */
@Composable
fun rememberQrScan(onResult: (String?) -> Unit): () -> Unit {
    val callback = rememberUpdatedState(onResult)
    val prompt = stringResource(R.string.scan_prompt)
    val launcher = rememberLauncherForActivityResult(ScanContract()) { r -> callback.value(r.contents) }
    return {
        launcher.launch(ScanOptions()
            .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
            .setPrompt(prompt)
            .setBeepEnabled(false)
            .setOrientationLocked(false))
    }
}

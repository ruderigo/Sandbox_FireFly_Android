package io.github.ruderigo.firefly.ui

import android.widget.Toast
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.ruderigo.firefly.R
import io.github.ruderigo.firefly.engine.Engine
import kotlinx.coroutines.flow.MutableStateFlow
import org.json.JSONObject

/**
 * Every way an address comes in -- a QR code scanned in Find Stumps or Chats, one typed, an
 * lxmf:// link tapped ("Open in FireFly" on a Stump's /address page, Stump 1.0.0-beta.52) --
 * goes through here, so it lands in the right place: the Stumps list or Chats.
 * The engine decides at once when it can (the link says so, a Stump already known, a Stump
 * on this Wi-Fi proving it); otherwise one tap: "A Stump or a person?".
 */
object AddressIntake {
    /** text: what was read; prefer: what to take when the engine can't tell (Find Stumps: "stump"). */
    data class Request(val text: String, val prefer: String? = null)
    val pending = MutableStateFlow<Request?>(null)
    fun submit(text: String, prefer: String? = null) { pending.value = Request(text, prefer) }
}

@Composable
fun AddressHandler(onStump: (String) -> Unit, onPerson: (String) -> Unit) {
    val ctx = LocalContext.current
    val req by AddressIntake.pending.collectAsState()
    var checking by remember { mutableStateOf(false) }
    var asking by remember { mutableStateOf<JSONObject?>(null) }       // the check said "ask"
    var refused by remember { mutableStateOf<String?>(null) }
    var adding by remember { mutableStateOf<Pair<String, String>?>(null) }   // (text, kind)

    LaunchedEffect(req) {
        val r = req ?: return@LaunchedEffect
        checking = true
        val c = Engine.obj("address_check", r.text)        // at most about a second (the Wi-Fi check)
        checking = false
        AddressIntake.pending.value = null
        when (c.optString("kind")) {
            "stump", "person" -> adding = r.text to c.optString("kind")
            "ask" -> if (r.prefer != null) adding = r.text to r.prefer
                     else asking = c.put("text", r.text)
            else -> refused = c.optString("error").takeIf { it.isNotBlank() && it != "null" }
                ?: ctx.getString(R.string.scan_not_address, r.text.trim().take(40))
        }
    }
    LaunchedEffect(adding) {
        val (text, kind) = adding ?: return@LaunchedEffect
        val r = Engine.obj("address_add", text, kind)
        adding = null
        val err = r.optString("error").takeIf { it.isNotBlank() && it != "null" }
        if (err != null) { refused = err; return@LaunchedEffect }
        if (r.optString("kind") == "stump") {
            val short = "<" + r.optString("key").substringAfter(":").take(8) + ">"
            Toast.makeText(ctx, ctx.getString(if (r.optBoolean("new")) R.string.add_stump_added else R.string.add_stump_known, short),
                Toast.LENGTH_LONG).show()
            onStump(r.optString("key"))
        } else onPerson(r.optString("peer"))
    }

    if (checking || adding != null) androidx.compose.material3.AlertDialog(
        onDismissRequest = {}, containerColor = Amber.Panel, shape = Large,
        properties = androidx.compose.ui.window.DialogProperties(dismissOnClickOutside = false, dismissOnBackPress = false),
        text = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                androidx.compose.material3.CircularProgressIndicator(Modifier.size(20.dp), color = Amber.Ember, strokeWidth = 2.dp)
                Spacer(Modifier.width(12.dp))
                Text(stringResource(R.string.address_checking), style = MaterialTheme.typography.bodyMedium)
            }
        }, confirmButton = {})

    asking?.let { a ->
        val short = "<" + a.optString("address").take(8) + ">"
        val suggest = a.optString("suggest", "stump")
        fun choose(kind: String) { asking = null; adding = a.optString("text") to kind }
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { asking = null }, containerColor = Amber.Panel, shape = Large,
            title = { Text(stringResource(R.string.address_ask_title), style = MaterialTheme.typography.titleMedium) },
            text = { Text(stringResource(R.string.address_ask_body, short), style = MaterialTheme.typography.bodyMedium) },
            confirmButton = {
                Row {
                    for (kind in if (suggest == "person") listOf("stump", "person") else listOf("person", "stump")) {
                        val primary = kind == suggest
                        Text(stringResource(if (kind == "stump") R.string.address_is_stump else R.string.address_is_person),
                            modifier = Modifier.clip(Small).clickable { choose(kind) }.padding(10.dp),
                            style = MaterialTheme.typography.labelLarge.copy(color = if (primary) Amber.Ember else Amber.Muted))
                    }
                }
            },
            dismissButton = {
                Text(stringResource(R.string.cancel), modifier = Modifier.clip(Small).clickable { asking = null }.padding(10.dp),
                    style = MaterialTheme.typography.labelLarge.copy(color = Amber.Muted))
            })
    }

    refused?.let { why ->
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { refused = null }, containerColor = Amber.Panel, shape = Large,
            title = { Text(stringResource(R.string.address_refused_title), style = MaterialTheme.typography.titleMedium) },
            text = { Text(why, style = MaterialTheme.typography.bodyMedium) },
            confirmButton = {
                Text(stringResource(R.string.address_ok), modifier = Modifier.clip(Small).clickable { refused = null }.padding(10.dp),
                    style = MaterialTheme.typography.labelLarge.copy(color = Amber.Ember))
            })
    }
}

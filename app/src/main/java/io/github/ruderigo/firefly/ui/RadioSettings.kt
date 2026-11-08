package io.github.ruderigo.firefly.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.ruderigo.firefly.R
import io.github.ruderigo.firefly.engine.Engine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

/*
 * The radio's channel and announcing, in the Network tab's LoRa radio box (Nov 2026; they were
 * in Settings). Each saves through the engine and says so in place, under its Save: "Saved",
 * then for a channel "retuning the RNode…" and the RNode's own answer.
 */

/** Saved settings and a way to save, with the confirmation shown where it was asked. */
private class Saver(val s: JSONObject, val commit: (JSONObject, String) -> Unit, val show: (String, Boolean) -> Unit)

@Composable
private fun rememberSaver(): Pair<Saver, Pair<String, Boolean>?> {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var reloadKey by remember { mutableIntStateOf(0) }
    val s by produceState(JSONObject(), reloadKey) { value = Engine.obj("settings_get") }
    var note by remember { mutableStateOf<Pair<String, Boolean>?>(null) }
    var noteId by remember { mutableIntStateOf(0) }
    val show: (String, Boolean) -> Unit = { t, ok -> note = t to ok; noteId++ }
    val commit: (JSONObject, String) -> Unit = { patch, okText ->
        scope.launch {
            val ok = withContext(Dispatchers.IO) { Engine.callOk("settings_set", patch.toString()) }
            if (ok) { show(okText, true); reloadKey++ } else show(ctx.getString(R.string.settings_failed), false)
        }
    }
    LaunchedEffect(noteId) { if (note != null) { delay(if (note?.first == ctx.getString(R.string.radio_retuning)) 45_000 else 4000); note = null } }
    return Saver(s, commit, show) to note
}

@Composable
private fun SavedNote(note: Pair<String, Boolean>?) {
    val (text, ok) = note ?: return
    Text((if (ok) "✓  " else "") + text, style = MaterialTheme.typography.labelMedium.copy(color = if (ok) Amber.Ember else Amber.Error),
        modifier = Modifier.padding(top = 6.dp))
}

/** The radio channel: frequency, bandwidth, SF, CR, power; done only once the RNode confirms it. */
@Composable
fun RadioChannelEditor() {
    val ctx = LocalContext.current
    val (saver, note) = rememberSaver()
    val s = saver.s
    val status by Engine.status.collectAsState()
    if (s.length() == 0) return
    val radio = s.getJSONObject("radio")
    fun show(text: String, ok: Boolean = true) = saver.show(text, ok)
    fun commitSettings(patch: JSONObject, okText: String = ctx.getString(R.string.settings_saved)) = saver.commit(patch, okText)
    // A new radio channel is "done" only when the RNode itself reports it: saved, then
    // "retuning…", then the RNode's answer (confirmed, what it reports instead, or none).
    var retuneTo by remember { mutableStateOf<Long?>(null) }          // the frequency asked (Hz)
    LaunchedEffect(retuneTo) {
        val want = retuneTo ?: return@LaunchedEffect
        val started = System.currentTimeMillis() / 1000.0
        val end = System.currentTimeMillis() + 45_000
        while (System.currentTimeMillis() < end) {
            delay(500)
            val r = Engine.status.value.optJSONObject("radio") ?: continue
            val st = r.optString("state")
            val fresh = r.optDouble("since", 0.0) >= started - 1          // happened after this save
            if (st == "connecting" || r.optBoolean("busy")) continue
            if (st == "online" && r.optBoolean("confirmed") && Math.abs(r.optLong("frequency") - want) <= 100) {
                show(ctx.getString(R.string.radio_confirmed, "%.3f".format(want / 1e6)), ok = true); retuneTo = null; return@LaunchedEffect
            }
            if (st == "refused" && fresh) { show(r.optString("detail"), ok = false); retuneTo = null; return@LaunchedEffect }
            if (st in listOf("off", "no devices")) { show(ctx.getString(R.string.radio_saved_no_rnode), ok = true); retuneTo = null; return@LaunchedEffect }
        }
        show(ctx.getString(R.string.radio_not_confirmed), ok = false)
        retuneTo = null
    }

    // ---------------------------------------------------------- Radio channel (Save)
    val savedFreq = "%.3f".format(java.util.Locale.ROOT, radio.optLong("frequency") / 1e6)
    val savedBw = radio.optInt("bandwidth")
    val savedSf = radio.optInt("spreading_factor").toString()
    val savedCr = radio.optInt("coding_rate").toString()
    val savedTxp = radio.optInt("tx_power").toString()
    var freq by remember(s) { mutableStateOf(savedFreq) }
    var bw by remember(s) { mutableIntStateOf(savedBw) }
    var sf by remember(s) { mutableStateOf(savedSf) }
    var cr by remember(s) { mutableStateOf(savedCr) }
    var txp by remember(s) { mutableStateOf(savedTxp) }
    val f = freq.replace(',', '.').toDoubleOrNull()
    val radioValid = f != null && f in 137.0..1020.0 && (sf.toIntOrNull() ?: 0) in 5..12 &&
        (cr.toIntOrNull() ?: 0) in 5..8 && (txp.toIntOrNull() ?: -1) in 0..22
    val radioDirty = freq.replace(',', '.').toDoubleOrNull()?.let { "%.3f".format(java.util.Locale.ROOT, it) } != savedFreq ||
        bw != savedBw || sf != savedSf || cr != savedCr || txp != savedTxp
    Column {
        Text(stringResource(R.string.radio_channel), style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(top = 14.dp, bottom = 6.dp))
        Text(stringResource(R.string.radio_match_warning), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(bottom = 6.dp))
        Labeled(stringResource(R.string.frequency_mhz)) { Field(freq, { freq = it }, Modifier.fillMaxWidth(), mono = true, number = true) }
        Labeled(stringResource(R.string.bandwidth)) {
            Row(Modifier.fillMaxWidth()) { BANDWIDTHS.forEach { b -> Chip("${b / 1000}", b == bw) { bw = b } } }
        }
        Row {
            Labeled("SF", Modifier.weight(1f)) { Field(sf, { sf = it }, Modifier.fillMaxWidth(), mono = true, number = true) }
            Spacer(Modifier.width(8.dp))
            Labeled("CR 4/", Modifier.weight(1f)) { Field(cr, { cr = it }, Modifier.fillMaxWidth(), mono = true, number = true) }
            Spacer(Modifier.width(8.dp))
            Labeled("dBm", Modifier.weight(1f)) { Field(txp, { txp = it }, Modifier.fillMaxWidth(), mono = true, number = true) }
        }
        Text(stringResource(R.string.stump_defaults_fill), modifier = Modifier.padding(top = 6.dp).clip(Small)
            .clickable { freq = "915.000"; bw = 125_000; sf = "8"; cr = "5"; txp = "7" }.padding(vertical = 4.dp),
            style = MaterialTheme.typography.labelMedium.copy(color = Amber.Ember))
        OnAir(status)
        SaveRow(dirty = radioDirty, valid = radioValid, problem = R.string.radio_invalid,
            onDiscard = { freq = savedFreq; bw = savedBw; sf = savedSf; cr = savedCr; txp = savedTxp }) {
            commitSettings(JSONObject().put("radio", JSONObject()
        .put("frequency", Math.round((f ?: 915.0) * 1e6)).put("bandwidth", bw)
        .put("spreading_factor", sf.toInt()).put("coding_rate", cr.toInt()).put("tx_power", txp.toInt())),
        ctx.getString(R.string.radio_retuning))
            retuneTo = Math.round((f ?: 915.0) * 1e6)
        }
        SavedNote(note)
    }
}

/** Announcing: how often FireFly says it's here. */
@Composable
fun AnnouncingSection() {
    val ctx = LocalContext.current
    val (saver, note) = rememberSaver()
    val s = saver.s
    if (s.length() == 0) return
    fun commitSettings(patch: JSONObject, okText: String = ctx.getString(R.string.settings_saved)) = saver.commit(patch, okText)
    // ---------------------------------------------------------- Announcing (Save)
    val savedAnnounce = s.optInt("announce_interval_min").toString()
    var announce by remember(s) { mutableStateOf(savedAnnounce) }
    Section(stringResource(R.string.announcing)) {
        Labeled(stringResource(R.string.announce_every)) {
            Field(announce, { announce = it }, Modifier.width(100.dp), mono = true, number = true)
        }
        Text(stringResource(R.string.announce_help), style = MaterialTheme.typography.bodySmall)
        SaveRow(dirty = announce != savedAnnounce, valid = (announce.toIntOrNull() ?: -1) in 0..1440,
            problem = R.string.announce_invalid, onDiscard = { announce = savedAnnounce }) {
            commitSettings(JSONObject().put("announce_interval_min", announce.toInt()))
        }
        SavedNote(note)
    }
}

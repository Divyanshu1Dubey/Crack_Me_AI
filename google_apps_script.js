/**
 * CrackCMS → Google Sheets Data Export (Auto-Sync Ready)
 * 
 * SETUP (takes 2 minutes):
 * ========================
 * 1. Open any Google Spreadsheet (or create a new one)
 * 2. Go to Extensions → Apps Script
 * 3. Delete any existing code, paste this ENTIRE file, click Save (💾)
 * 4. Update BACKEND_URL and ADMIN_CREDENTIALS below with your values
 * 5. Click ▶ Run → select "exportAllData" → Run (grant permissions when asked)
 * 6. Go back to your Spreadsheet — 5 sheets will appear with all your data!
 *
 * AUTO-SYNC (optional):
 * 7. In Apps Script, click ⏰ Triggers (left sidebar, clock icon)
 * 8. Click "+ Add Trigger" (bottom right)
 * 9. Settings: Function = "exportAllData", Event = "Time-driven", 
 *    Type = "Day timer", Time = pick any time → Save
 * 10. Done! Data syncs automatically every day.
 *
 * Sheets created: Users, Token Balances, Token Transactions, Feedback, Sync Info
 */

// ═══════════ CONFIGURATION — UPDATE THESE ═══════════
var BACKEND_URL = 'https://crackcms-vsthc.ondigitalocean.app';
var ADMIN_CREDENTIALS = {
  username: 'admin',         // ← your Django superuser username
  password: 'Kali2712@'  // ← your Django superuser password
};
// ═════════════════════════════════════════════════════

/**
 * Get JWT access token from the backend
 */
function getAuthToken_() {
  var url = BACKEND_URL + '/api/auth/login/';
  var options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(ADMIN_CREDENTIALS),
    muteHttpExceptions: true
  };
  var response = UrlFetchApp.fetch(url, options);
  var code = response.getResponseCode();
  if (code !== 200) {
    throw new Error('Login failed (HTTP ' + code + '). Check your username/password.');
  }
  var body = JSON.parse(response.getContentText());
  // Django SimpleJWT returns { tokens: { access, refresh } }
  if (body.tokens && body.tokens.access) return body.tokens.access;
  if (body.access) return body.access;
  throw new Error('Unexpected login response — no access token found.');
}

/**
 * Fetch all export data from the backend
 */
function fetchExportData_(token) {
  var url = BACKEND_URL + '/api/analytics/export/?type=all';
  var options = {
    method: 'get',
    headers: { 'Authorization': 'Bearer ' + token },
    muteHttpExceptions: true
  };
  var response = UrlFetchApp.fetch(url, options);
  var code = response.getResponseCode();
  if (code === 403) throw new Error('Export denied — your account is not an admin.');
  if (code !== 200) throw new Error('Export failed (HTTP ' + code + '): ' + response.getContentText().substring(0, 300));
  return JSON.parse(response.getContentText());
}

/**
 * Write an array of objects to a named sheet with styled headers
 */
function writeToSheet_(sheetName, data, headers, headerLabels) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
  }
  sheet.clearContents();
  sheet.clearFormats();

  var labels = headerLabels || headers;

  // Header row
  sheet.getRange(1, 1, 1, labels.length).setValues([labels]);
  sheet.getRange(1, 1, 1, labels.length)
    .setFontWeight('bold')
    .setBackground('#4a90d9')
    .setFontColor('#ffffff')
    .setHorizontalAlignment('center');

  if (!data || data.length === 0) {
    sheet.getRange(2, 1).setValue('No data yet').setFontStyle('italic');
    return;
  }

  // Data rows
  var rows = data.map(function(item) {
    return headers.map(function(h) {
      var val = item[h];
      if (val === null || val === undefined) return '';
      if (val === true) return 'Yes';
      if (val === false) return 'No';
      return val;
    });
  });
  sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);

  // Alternate row colors for readability
  for (var r = 2; r <= rows.length + 1; r++) {
    if (r % 2 === 0) {
      sheet.getRange(r, 1, 1, headers.length).setBackground('#f0f4ff');
    }
  }

  // Freeze header row + auto-resize
  sheet.setFrozenRows(1);
  for (var i = 1; i <= headers.length; i++) {
    sheet.autoResizeColumn(i);
  }
}

/**
 * Show alert only when run manually (not from trigger)
 */
function showMessage_(msg) {
  try {
    SpreadsheetApp.getUi().alert(msg);
  } catch (e) {
    // Running from time-trigger — UI not available, just log it
    Logger.log(msg);
  }
}

/**
 * ▶ MAIN FUNCTION — Run this manually OR it runs automatically via trigger
 */
function exportAllData() {
  try {
    Logger.log('CrackCMS export started at ' + new Date().toISOString());

    var token = getAuthToken_();
    var data = fetchExportData_(token);

    // ── 1. Users sheet ──
    if (data.users) {
      writeToSheet_('Users', data.users,
        ['id', 'username', 'email', 'first_name', 'last_name', 'is_admin', 'date_joined', 'last_login'],
        ['ID', 'Username', 'Email', 'First Name', 'Last Name', 'Admin?', 'Date Joined', 'Last Login']
      );
    }

    // ── 2. Token Balances sheet ──
    if (data.token_balances) {
      writeToSheet_('Token Balances', data.token_balances,
        ['username', 'purchased_tokens', 'feedback_credits', 'available'],
        ['Username', 'Purchased Tokens', 'Feedback Credits', 'Available']
      );
    }

    // ── 3. Token Transactions sheet ──
    if (data.token_transactions) {
      writeToSheet_('Token Transactions', data.token_transactions,
        ['username', 'type', 'amount', 'note', 'created_at'],
        ['Username', 'Type', 'Amount', 'Note', 'Date']
      );
    }

    // ── 4. Feedback sheet ──
    if (data.feedback) {
      writeToSheet_('Feedback', data.feedback,
        ['username', 'category', 'rating', 'title', 'message', 'is_read', 'admin_reply', 'created_at'],
        ['Username', 'Category', 'Rating', 'Title', 'Message', 'Read?', 'Admin Reply', 'Date']
      );
    }

    // ── 5. Sync Info sheet ──
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var metaSheet = ss.getSheetByName('Sync Info');
    if (!metaSheet) metaSheet = ss.insertSheet('Sync Info');
    metaSheet.clearContents();
    metaSheet.getRange(1, 1).setValue('Last Synced').setFontWeight('bold');
    metaSheet.getRange(1, 2).setValue(new Date().toLocaleString());
    metaSheet.getRange(2, 1).setValue('Users').setFontWeight('bold');
    metaSheet.getRange(2, 2).setValue(data.users ? data.users.length : 0);
    metaSheet.getRange(3, 1).setValue('Token Balances').setFontWeight('bold');
    metaSheet.getRange(3, 2).setValue(data.token_balances ? data.token_balances.length : 0);
    metaSheet.getRange(4, 1).setValue('Transactions').setFontWeight('bold');
    metaSheet.getRange(4, 2).setValue(data.token_transactions ? data.token_transactions.length : 0);
    metaSheet.getRange(5, 1).setValue('Feedback').setFontWeight('bold');
    metaSheet.getRange(5, 2).setValue(data.feedback ? data.feedback.length : 0);
    metaSheet.autoResizeColumn(1);
    metaSheet.autoResizeColumn(2);

    var summary = 'Export complete! ' +
      (data.users ? data.users.length : 0) + ' users, ' +
      (data.token_balances ? data.token_balances.length : 0) + ' balances, ' +
      (data.token_transactions ? data.token_transactions.length : 0) + ' transactions, ' +
      (data.feedback ? data.feedback.length : 0) + ' feedback entries.';

    Logger.log(summary);
    showMessage_(summary);

  } catch (e) {
    Logger.log('CrackCMS export ERROR: ' + e.message);
    showMessage_('Export error: ' + e.message);
  }
}

/**
 * Adds "CrackCMS" menu to the spreadsheet toolbar
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🎓 CrackCMS')
    .addItem('📥 Sync All Data Now', 'exportAllData')
    .addToUi();
}

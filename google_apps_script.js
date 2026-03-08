/**
 * CrackCMS → Google Sheets Data Export
 * 
 * SETUP INSTRUCTIONS:
 * ==================
 * 1. Open Google Sheets → Extensions → Apps Script
 * 2. Delete any existing code and paste this entire file
 * 3. Update BACKEND_URL and ADMIN_CREDENTIALS below
 * 4. Click "Run" → "exportAllData" to test (grant permissions when prompted)
 * 5. To auto-run daily: Triggers (clock icon) → Add Trigger →
 *    Function: exportAllData, Event source: Time-driven, Day timer, pick time
 *
 * The script will create/update 4 sheets: Users, Token Balances, Token Transactions, Feedback
 */

// ========== CONFIGURATION ==========
const BACKEND_URL = 'https://crackcms-backend.onrender.com';
const ADMIN_CREDENTIALS = {
  username: 'admin',      // your Django superuser username
  password: 'admin123'    // your Django superuser password
};
// ====================================

/**
 * Get JWT token from backend
 */
function getAuthToken() {
  const url = BACKEND_URL + '/api/accounts/login/';
  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(ADMIN_CREDENTIALS),
    muteHttpExceptions: true
  };
  const response = UrlFetchApp.fetch(url, options);
  if (response.getResponseCode() !== 200) {
    throw new Error('Login failed: ' + response.getContentText());
  }
  const data = JSON.parse(response.getContentText());
  return data.tokens ? data.tokens.access : data.access;
}

/**
 * Fetch export data from backend
 */
function fetchExportData(token) {
  const url = BACKEND_URL + '/api/analytics/export/?type=all';
  const options = {
    method: 'get',
    headers: { 'Authorization': 'Bearer ' + token },
    muteHttpExceptions: true
  };
  const response = UrlFetchApp.fetch(url, options);
  if (response.getResponseCode() !== 200) {
    throw new Error('Export failed (' + response.getResponseCode() + '): ' + response.getContentText());
  }
  return JSON.parse(response.getContentText());
}

/**
 * Write array of objects to a named sheet
 */
function writeToSheet(sheetName, data, headers) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
  }
  sheet.clearContents();

  if (!data || data.length === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#4a90d9').setFontColor('#ffffff');
    return;
  }

  // Header row
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#4a90d9').setFontColor('#ffffff');

  // Data rows
  const rows = data.map(function(item) {
    return headers.map(function(h) {
      var val = item[h];
      return val === null || val === undefined ? '' : val;
    });
  });
  sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);

  // Auto-resize columns
  for (var i = 1; i <= headers.length; i++) {
    sheet.autoResizeColumn(i);
  }
}

/**
 * Main export function — run this manually or via trigger
 */
function exportAllData() {
  try {
    const token = getAuthToken();
    const data = fetchExportData(token);

    // Users sheet
    if (data.users) {
      writeToSheet('Users', data.users, [
        'id', 'username', 'email', 'first_name', 'last_name',
        'is_admin', 'date_joined', 'last_login'
      ]);
    }

    // Token Balances sheet
    if (data.token_balances) {
      writeToSheet('Token Balances', data.token_balances, [
        'username', 'purchased_tokens', 'feedback_credits', 'available'
      ]);
    }

    // Token Transactions sheet
    if (data.token_transactions) {
      writeToSheet('Token Transactions', data.token_transactions, [
        'username', 'type', 'amount', 'note', 'created_at'
      ]);
    }

    // Feedback sheet
    if (data.feedback) {
      writeToSheet('Feedback', data.feedback, [
        'username', 'category', 'rating', 'title', 'message',
        'is_read', 'admin_reply', 'created_at'
      ]);
    }

    // Update timestamp
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let metaSheet = ss.getSheetByName('Sync Info');
    if (!metaSheet) metaSheet = ss.insertSheet('Sync Info');
    metaSheet.clearContents();
    metaSheet.getRange(1, 1).setValue('Last synced').setFontWeight('bold');
    metaSheet.getRange(1, 2).setValue(new Date().toLocaleString());
    metaSheet.getRange(2, 1).setValue('Records').setFontWeight('bold');
    metaSheet.getRange(2, 2).setValue(
      'Users: ' + (data.users ? data.users.length : 0) +
      ' | Balances: ' + (data.token_balances ? data.token_balances.length : 0) +
      ' | Transactions: ' + (data.token_transactions ? data.token_transactions.length : 0) +
      ' | Feedback: ' + (data.feedback ? data.feedback.length : 0)
    );

    SpreadsheetApp.getUi().alert('Export complete! Check all sheets.');
  } catch (e) {
    SpreadsheetApp.getUi().alert('Export error: ' + e.message);
    Logger.log('Export error: ' + e.message);
  }
}

/**
 * Add a custom menu to the spreadsheet
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('CrackCMS')
    .addItem('Sync Data Now', 'exportAllData')
    .addToUi();
}

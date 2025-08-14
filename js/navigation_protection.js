// Navigation Protection Script
// Protects against accidental navigation when there are unsaved changes

// Global variable to track unsaved changes state
window.hasUnsavedChanges = false;

// Function to update the unsaved changes status from Python
window.updateUnsavedChangesStatus = function(status) {
    window.hasUnsavedChanges = status;
};

// Override NiceGUI navigation to check for unsaved changes
window.originalNavigate = window.location.assign;
window.location.assign = function(url) {
    if (window.hasUnsavedChanges) {
        if (confirm('You have unsaved changes. Are you sure you want to leave this page?')) {
            window.originalNavigate(url);
        }
    } else {
        window.originalNavigate(url);
    }
};

// Also protect history navigation
window.addEventListener('popstate', function(event) {
    if (window.hasUnsavedChanges) {
        if (!confirm('You have unsaved changes. Are you sure you want to leave this page?')) {
            event.preventDefault();
            window.history.pushState(null, null, window.location.href);
        }
    }
});

// Protect against page reload (F5, Ctrl+R, etc.)
window.addEventListener('beforeunload', function(event) {
    if (window.hasUnsavedChanges) {
        event.preventDefault();
        event.returnValue = 'You have unsaved changes. Are you sure you want to reload this page?';
        return 'You have unsaved changes. Are you sure you want to reload this page?';
    }
});

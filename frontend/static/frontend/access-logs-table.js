window.initAccessLogsTable = function() {
    if (!window.initFilterableTable) return;
    window.initFilterableTable({
        tableId: "accessLogsTable",
        optionsPrefix: "accessLogs",
        rowSelector: "#accessLogsTableBody tr",
        globalSearchId: "accessLogsGlobalSearch",
        resetAllId: "accessLogsResetAllFilters",
        noResultsId: "accessLogsNoResults",
        countTotalId: "accessLogsTotalCount",
        countVisibleId: "accessLogsVisibleCount",
        columnVisibility: {
            buttonId: "toggleAccessLogsColumnsBtn",
            menuId: "accessLogsColumnVisibilityMenu",
            storageKey: "gatecoreAccessLogsTable",
            enableReorder: false,
            resetBannerId: "accessLogsColumnResetBanner",
        },
    });
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function() {
        window.initAccessLogsTable?.();
    });
} else {
    window.initAccessLogsTable?.();
}

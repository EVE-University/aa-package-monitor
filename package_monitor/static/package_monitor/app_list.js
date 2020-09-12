$(document).ready(function () {

    /* retrieve generated data from HTML page */
    var elem = document.getElementById('dataExport');
    var listDataUrl = elem.getAttribute('data-listDataUrl');

    /* dataTable def */
    $('#tab_app_list').DataTable({
        ajax: {
            url: listDataUrl,
            dataSrc: '',
            cache: false
        },

        columns: [
            { data: 'name_link' },
            { data: 'current' },
            { data: 'latest' },
            { data: 'description' },
            { data: 'apps' },

            { data: 'is_outdated_str' },
            { data: 'has_apps_str' }
        ],

        ordering: false,

        columnDefs: [
            { "sortable": false, "targets": [0, 1, 2, 3, 4] },
            { "visible": false, "targets": [5, 6] }
        ],

        paging: false,

        filterDropDown:
        {
            columns: [
                {
                    idx: 5,
                    title: "Outdated?"
                },
                {
                    idx: 6,
                    title: "Has Django Apps?"
                }
            ],
            bootstrap: true
        },

        rowCallback: function (row, data, index) {
            if (data['is_outdated']) {
                $(row).addClass('warning');
                $(row).find('td:eq(2)').css('font-weight', 'bold')
            }
        }

    });
});
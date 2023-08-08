let totalRecords = 0;
let totalPages = 0;

/** Fetch list of risks with provided filters and skip parameter,
 * count total pages and render results.
 * * @param {number} skip - Number of items to skip
 * */
async function fetchRisks(skip= 0) {
    let filters = getFilterValues();
    await fetch(`api/risks?skip=${skip}&${filters}`)
        .then((response) => {
            if(!response.ok) {
                return response.text().then(text => { throw new Error(text) })
            } else {
                return response.json();
            }
        })
        .then((data) => {
            totalRecords = data.count;
            totalPages = Math.ceil(totalRecords / perPage);
            showTenders(data);
        })
        .catch((error) => {
            console.error("Error:", error);
            document.body.insertAdjacentHTML(
                'beforebegin',
                `<div class="alert alert-danger alert-dismissible fade show position-fixed z-999 w-100" role="alert">
                  ${error.message}
                  <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close">
                </div>`
            )

        });
}

/** Fetch list of risks, create pagination and update url for downloading results */
async function filterRisks() {
    await fetchRisks().then(() => createPagination(0));
    document.getElementById('downloadReport').href = getDownloadReportURL();
}

/** Handle filling tenders' table with result or render empty state */
function showTenders(data) {
    if (totalRecords) {
        document.getElementById("emptyData").style.display = 'none';
        document.getElementById("tendersTable").innerHTML = createTableContent(data);
    } else {
        document.getElementById("tendersTable").innerHTML = '';
        document.getElementById("emptyData").style.display = 'block';
    }
}

// Load filters

/** Fetch filter data to fill all filters inputs and selects */
async function fetchFilterData() {
    await fetch(`api/filter-values`)
        .then((response) => response.json())
        .then((data) => {
            let regionOptions = '';
            for (let item of data.regions) {
                regionOptions += `<option value="${item}">${item}</option>`
            }
            document.getElementById('regions').innerHTML = regionOptions;
            let risksOptions = '';
            for (let item of data.risk_rules) {
                risksOptions += `<option value="${item.identifier}">
                  ${item.identifier} ${item.status === 'archived' ? '(архів)' : ''}
                </option>`
            }
            document.getElementById('risks').innerHTML = risksOptions;
        })
        .catch((error) => {
            console.error("Error:", error);
        });
}

/** Clear all filters inputs and fetch frssh list of risks */
function clearFilters() {
    document.getElementById('regions').selectedIndex = -1;
    document.getElementById('risks').selectedIndex = -1;
    document.getElementById('edrpou').value = '';
    document.getElementById('tender_id').value = '';
    document.getElementById('sorting').selectedIndex = 0;
    document.getElementById('risksAll').checked = false;
    filterRisks();
}

/** Create url for downloading filtered results */
function getDownloadReportURL() {
    let filters = getFilterValues();
    return `api/risks-report?${filters}`;
}

function getValue(field) {
    return field ? field : '-'
}
/** Create tenders' table content with provided data
 * * @param {object} data - Data fetched from API
 * */
function createTableContent(data) {
    let header =
        `<thead>
                  <tr>
                      <th scope="col">ID</th>
                      <th scope="col" width="23%">Tender ID</th>
                      <th scope="col" width="20%">Замовник</th>
                      <th scope="col">Регіон</th>
                      <th scope="col">ЄДРПОУ</th>
                      <th scope="col">Вартість</th>
                      <th scope="col">Дата перевірки</th>
                      <th scope="col">Ризики</th>
                 </tr>
            </thead>`;

    let body = `<tbody class="table-group-divider">`;

    // Loop to access all rows
    for (let item of data.items) {
        body += `<tr> 
                <td>${item._id} </td>
                <td>${getValue(item.tenderID)} </td>
                <td>${getValue(item.procuringEntity?.name)}</td>
                <td>${getValue(item.procuringEntity?.address?.region)}</td> 
                <td>${getValue(item.procuringEntity?.identifier?.id)}</td>  
                <td>${getValue(item.value?.amount)} ${item.value?.currency ? item.value?.currency : ''}</td>    
                <td>${new Date(item.dateAssessed).toLocaleString()}</td>      
                <td class="text-center">
                  <button class="btn btn-link py-0" type="button" data-bs-toggle="collapse" data-bs-target="#accordion-${item._id}" aria-controls=="accordion-${item._id}" aria-expanded="false">
                    <i class="bi bi-three-dots"></i>
                  </button>
                </td>
            </tr>
            <tr>
                <td colspan="7" class="p-0 border-bottom-0 w-100">
                    <div id="accordion-${item._id}" class="collapse mx-5">
                        <table class="table">
                          <thead>
                              <tr>
                                  <th scope="col" width="10%">id</th>
                                  <th scope="col">Назва ризику</th>
                                  <th scope="col" width="15%" class="text-center">
                                  Індикатор
                                  <p class="my-0"><small>
                                    (<i class="bi bi-check-circle text-success"></i> - 0, <i class="bi bi-exclamation-triangle text-danger"></i> - 1)
                                  </small></p>
                                  </th>
                                  <th scope="col" width="30%">Дата</th>
                                  <th scope="col" width="20%">Об'єкт перевірки</th>
                               </tr>
                          </thead>
                        <tbody>`;
        for (let [key, items] of Object.entries(item.risks)) {
            // TODO: Leave only array processing
            if (Array.isArray(items)) {
                for (let item of items) {
                    body += `<tr>
                        <td>${key}</td>
                        <td>${item.name}</td>
                        <td class="text-center">
                        ${item.indicator === 'risk_found' ? 
                        `<i class="bi bi-exclamation-triangle text-danger"></i>` : 
                        `<i class="bi bi-check-circle text-success"></i>`}
                        </td>
                        <td>${item.date}</td>
                        <td>${item.item ? item.item.type + ' - ' + item.item.id : 'tender'}</td>
                     </tr>`;
                }
            } else {
                body += `<tr>
                    <td>${key}</td>
                    <td>${items.name}</td>
                    <td class="text-center">
                    ${items.indicator === 'risk_found' ? 
                    `<i class="bi bi-exclamation-triangle text-danger"></i>` : 
                    `<i class="bi bi-check-circle text-success"></i>`}
                    </td>
                    <td>${items.date}</td>
                    <td>${items.item ? items.item.type + ' - ' + items.item.id : 'tender'}</td>
                 </tr>`;
            }
        }
        body += `</tbody></table></div></td></tr>`;
    }
    body += `</tbody>`;
    return header + body
}

/** Get values from filter inputs and selects, create object with filters
 * and return query string ready for API call
 * */
function getFilterValues() {
    let regionOptions = document.getElementById('regions').selectedOptions;
    let regionValues = Array.from(regionOptions).map(({ value }) => value);
    let risksOptions = document.getElementById('risks').selectedOptions;
    let risksAll = document.getElementById('risksAll').checked;
    let risksValues = Array.from(risksOptions).map(({ value }) => value);
    let edrpou = document.getElementById('edrpou').value;
    let tender_id = document.getElementById('tender_id').value;
    let sorting = document.getElementById('sorting').value.split('-');
    let filters = {
        tender_id,
        edrpou,
        region: regionValues.join(';'),
        risks: risksValues.join(';'),
        risks_all: risksAll,
        sort: sorting[0],
        order: sorting[1],
    };
    return Object.keys(filters).map(key => key + '=' + filters[key]).join('&')
}


// PAGINATION
const perPage = 20;

/**
 * Create pagination buttons with correct links and vent listeners.
 * @param {number} skip - Number of items to skip
 */
function createPagination(skip){
    let currentPage = skip / perPage + 1;
    let pageContainer = document.getElementById("pageContainer");
    pageContainer.innerHTML = "";

    if (totalRecords) {
        pageContainer.insertAdjacentHTML(
            'beforeend',
            `<li class='page-item ${currentPage === 1 ? 'disabled' : ''}' id="previousPage">
                <a href='#' class='page-link'>&laquo;</a>
              </li>`
        );
        if (currentPage !== 1) {
            document.getElementById("previousPage").addEventListener(
                "click", () => {
                    turnPage(currentPage - 1)
                }
            );
        }

        for (let i = 1; i <= 3; i++) {
            let page = skip / perPage + i;
            if (page <= totalPages) {
                pageContainer.insertAdjacentHTML(
                    'beforeend',
                    `<li class='page-item ${currentPage === page ? 'disabled' : ''}' id="page${i}">
                    <a href='#' class='page-link'>${page}</a>
                </li>`
                );
                if (currentPage !== page) {
                    document.getElementById(`page${i}`).addEventListener(
                        "click", () => {
                            turnPage(page)
                        }
                    );
                }
            }
        }

        pageContainer.insertAdjacentHTML(
            'beforeend',
            `<li class='page-item ${currentPage === totalPages ? 'disabled' : ''}' id="nextPage">
              <a href='#' class='page-link'>&raquo;</a>
            </li>`
        );
        if (currentPage !== totalPages) {
            document.getElementById("nextPage").addEventListener(
                "click", () => {
                    turnPage(currentPage + 1)
                }
            );
        }
    }
}

/** Fetch risks for page number and update pagination links */
function turnPage(pageNumber) {
    // First page is 1, but skip parameter for first page should be 0, that's why we do (pageNumber - 1)
    let skip = (pageNumber - 1) * perPage;
    createPagination(skip);
    fetchRisks(skip);
}

// init app
fetchFilterData();
filterRisks();

// set event listeners for filter buttons
document.getElementById('clearFilters').addEventListener('click', clearFilters);
document.getElementById("fetchRisks").addEventListener("click", filterRisks);

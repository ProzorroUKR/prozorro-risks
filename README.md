# Prozorro Risks API

System for processing tenders and contracts via risk-rules and for assessing indicators of risks depending on tender/contract structure.


## General risk information
Risk rules are classes with particular properties and functions for processing object and assessing indicator.

All risk rules: `src/prozorro/risks/rules`

Base risk class: `src/prozorro/risks/rules/base.py`

Risk rule has next properties:
* `identifier` - Identifier of risk rule, e.g. "sas-3-1", "bank-3-3"
* `name` - Risk name, e.g. "Невиконання замовником рішення органу оскарження"
* `owner` - Risk owner, by default "sas"
* `description` - Description of risk rule
* `legitimateness` - Legislative justification of the risk rule
* `development_basis` - The basis for the development of the risk rule
* `procurement_methods` - Possible procurement methods (procedure type). It is a set of strings: 
    ```
    procurement_methods = (
        "aboveThresholdEU",
        "aboveThresholdUA",
        "aboveThreshold",
    )
    ```
* `tender_statuses` - Set of tender statuses, on which risk rule is working
* `procurement_categories` - Set of procurement categories, on which risk rule is working
* `procuring_entity_kinds` - Set of procuring entity kind, on which risk rule is working
* `contract_statuses` - Set of contract statuses, on which risk rule is working. This property is required for risk rules which process contracts and follow contract's API
* `start_date` - Date from when risk rule has started. By default: "2023-01-01"
* `end_date` - Date till what date risk rule is working. After that date risk rule will be turned off.
* `stop_assessment_status` - Status on which risk rule stops processing tender and save previous result. For example for tender `stop_assessment_status = 'complete'`, for contract `stop_assessment_status = 'terminated'`

Each risk rule should have particular function for processing object whether the object for processing is a tender or a contract:
* process_tender
* process_contract

These functions have one required argument - JSON object (tender/contract body). And these functions should return one of 3 risk result classes:
* `RiskFound` - result where indicator is equal to 'risk_found'
* `RiskNotFound` - result where indicator is equal to 'risk_not_found'
* `RiskFromPreviousResult` - result where indicator is equal to 'use_previous_result'. This one is used when tender moves to `stop_assessment_status` - e.g it can be 'complete' for tenders, 'terminated' for contracts. That means risk engine takes previous processing result and save it to database. After that object isn't being processed in the future. The processing is completed.

All these risk result classes have next properties:
* indicator
* type
* id

Properties `type` and `id` are optional. They should be set if risk rule processes particular item. Every risk rule for contract should return these two properties too. For example:
```
async def process_contract(self, contract):
    ...
    return RiskFound(type="contract", id=contract["id"])
```

When `type` and `id` properties aren't set it means that tender has been processed in general.

# How to create your own risk rule
1) Create a new python file with naming as risk-identifier, in directory: `src/prozorro/risks/rules` E.g. new file `sas-3-15.py`
2) Create class for risk rule and obligatory inherit from `BaseTenderRiskRule` or `BaseContractRiskRule` (depends on what kind of object the risk-rule will be process)
    ```
    class RiskRule(BaseTenderRiskRule):
        ...
    ```
3) Set all properties for your class (identifier, name, procurement_methods, etc.)
4) Write logic for processing object in your class (functions `process_tender` or `process_contract`). These functions should return only `BaseRiskResult` instance (RiskFound, RiskNotFound, RiskFromPreviousResult). If your risk will be looking at particular items (not tender in general), then add to return results `type` and `id` of processing object (inside `BaseRiskResult`).
    ```
    async def process_contract(self, contract):
        ...
        return RiskFound(type="contract", id=contract["id"])
  
    ``` 
    or for tender in general:
    ```
    async def process_tender(self, tender):
        ...
        return RiskFound()
  
    ``` 
5) TO TURN ON YOUR RISK FOR CRAWLER: Add your risk by file name to: `src/prozorro/risks/rules/__init__.py`. Happy testing!

# Local development

Clone project on your local machine:
* via HTTPs: https://github.com/ProzorroUKR/prozorro-risks.git
* via CLI: `gh repo clone ProzorroUKR/prozorro-risks`

## System requirements
Install next requirements on your machine:
* make
* docker
* docker-compose

## Usage

### Run

To start the project in development mode, run the following command:

```
make run
```

or just

```
make start
```

To stop docker containers:

```
make stop
```

To clean up docker containers (removes containers, networks, volumes, and images created by docker-compose up):

```
make remove-compose
```

or just

```
make clean
```

Shell inside the running container

```
make bash # the command can be executed only if the server is running e.g. after `make run`
```

### Linters

To run flake8:

```
make lint
```

All the settings for `flake8` can be customized in `.flake8` file


### Env variables

There are few env variables that can be configured in docker-compose.yaml for local deployment:

* PUBLIC_API_HOST - link for tenders' and contracts' API host
(e.g. 'https://api.prozorro.gov.ua')

* FORWARD_CHANGES_COOLDOWN_SECONDS - time for crawler sleeping. It may be needed for optimizing tender processing. Tenders may be modified too often, for instance every 5 minutes. This configuration allows crawler to wait and not process too fresh tenders that might be modified in the nearest future one more time. This configuration is in seconds. 

E.g. to let crawler sleep for 10 hours and then process all tenders that had been modifying during this time:
```
FORWARD_CHANGES_COOLDOWN_SECONDS: '36000'
```
Or you can set `FORWARD_CHANGES_COOLDOWN_SECONDS: ''` for crawler not to sleep.

* FORWARD_OFFSET - timestamp from what period of time crawler starts processing tenders. 
E.g. 
```
FORWARD_OFFSET: '1672524000.0'  # 2023-01-01T00:00:00+02:00
```
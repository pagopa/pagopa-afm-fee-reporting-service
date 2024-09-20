#!/usr/local/bin/python3
import json
import logging
import os
import boto3
import azure.cosmos.cosmos_client as cosmos_client
import psycopg
import decimal


class Bundle:
    def __init__(self, psp_id,
                 psp_rag_soc,
                 codice_abi,
                 nome_servizio,
                 descrizione_canale_mod_pag,
                 inf_desc_serv,
                 inf_url_canale,
                 url_informazioni_psp,
                 importo_minimo,
                 importo_massimo,
                 costo_fisso,
                 canale_mod_pag_code,
                 tipo_vers_cod,
                 canale_mod_pag,
                 on_us,
                 carte,
                 conto,
                 altri_wisp,
                 altri_io,
                 is_duplicated,
                 conto_app):
        self.psp_id = psp_id
        self.psp_rag_soc = psp_rag_soc
        self.codice_abi = codice_abi
        self.nome_servizio = nome_servizio
        self.descrizione_canale_mod_pag = descrizione_canale_mod_pag
        self.inf_desc_serv = inf_desc_serv
        self.inf_url_canale = inf_url_canale
        self.url_informazioni_psp = url_informazioni_psp
        self.importo_minimo = importo_minimo
        self.importo_massimo = importo_massimo
        self.costo_fisso = costo_fisso
        self.canale_mod_pag_code = canale_mod_pag_code
        self.tipo_vers_cod = tipo_vers_cod
        self.canale_mod_pag = canale_mod_pag
        self.on_us = on_us
        self.carte = carte
        self.conto = conto
        self.altri_wisp = altri_wisp
        self.altri_io = altri_io
        self.is_duplicated = is_duplicated
        self.conto_app = conto_app


    def serialize_bundle(self) -> dict:

        mod_pag_code = float(self.canale_mod_pag_code) if isinstance(self.canale_mod_pag_code, decimal.Decimal) else 0
        return {
            "psp_id": str(self.psp_id),
            "psp_rag_soc": str(self.psp_rag_soc),
            "codice_abi": str(self.codice_abi),
            "nome_servizio": str(self.nome_servizio),
            "descrizione_canale_mod_pag": str(self.descrizione_canale_mod_pag),
            "inf_desc_serv": str(self.inf_desc_serv),
            "inf_url_canale": str(self.inf_url_canale),
            "url_informazioni_psp": str(self.url_informazioni_psp),
            "importo_minimo": self.importo_minimo,
            "importo_massimo": self.importo_massimo,
            "costo_fisso": self.costo_fisso,
            "canale_mod_pag_code": mod_pag_code,
            "tipo_vers_cod": str(self.tipo_vers_cod),
            "canale_mod_pag": str(self.canale_mod_pag),
            "on_us": self.on_us,
            "carte": self.carte,
            "conto": self.conto,
            "altri_wisp": self.altri_wisp,
            "altri_io": self.altri_io,
            "is_duplicated": self.is_duplicated,
            "conto_app": self.conto_app
        }


def bundles_equal(b1: Bundle, b2: Bundle) -> bool:
    return (b1.psp_id == b2.psp_id
            and b1.importo_massimo == b2.importo_massimo
            and b1.importo_minimo == b2.importo_minimo
            and b1.on_us == b2.on_us
            and b1.tipo_vers_cod == b2.tipo_vers_cod)


def get_pg_connection():
    logger.info("[get_pg_connection] getting postgres connection parameters")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")

    logger.info("[get_pg_connection] creating db connection...")
    connection = psycopg.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    logger.info("[get_pg_connection] db connection established")
    return connection


def get_wisp_bundles(connection):

    # read psp blacklisted
    psp_blacklist = os.getenv("PSP_BLACKLIST")
    psp_blacklist = psp_blacklist.split(",")

    # read psp abi table
    psp_abi_code = os.getenv("PSP_ABI_CODE")
    psp_code = json.loads(psp_abi_code)

    # get cdi_master data
    logger.info(f"[get_wisp_bundles] getting cdi master data")
    cdi_info = {}
    db_query = """select 
            p.id_psp,
            cm.data_inizio_validita,
            cm.url_informazioni_psp,
            cm.url_informativa_psp
        from
            cdi_master cm,
            psp p 
        where 1=1     
            and p.obj_id = cm.fk_psp
            and cm.data_inizio_validita = (select max(cm2.data_inizio_validita) from cdi_master cm2, psp p2 where cm2.fk_psp = p2.obj_id and p2.id_psp = p.id_psp)
        order by p.id_psp asc"""

    logger.info(f"[get_wisp_bundles] executing query [{db_query}]")
    cursor = connection.cursor()
    cursor.execute(db_query)
    dataset = cursor.fetchall()
    for data in dataset:
        psp_id = data[0]
        psp_url = data[2]
        cdi_info[psp_id] = psp_url

    logger.info("[get_wisp_bundles] CDI data loaded")

    logger.info("[get_wisp_bundles] loading bundles data")
    bundles = []
    db_query = """select
            es.psp_id,
            es.psp_rag_soc,
            es.codice_abi,
            es.nome_servizio,
            es.canale_mod_pag,
            es.inf_desc_serv,
            es.inf_url_canale,
            es.importo_minimo,
            es.importo_massimo,
            es.costo_fisso,
            es.tipo_vers_cod,
            es.canale_id,
            es.canale_app,
            es.carrello_carte
        from
            elenco_servizi es
        where 1=1
            and es.codice_lingua = 'IT'
            and es.psp_id NOT LIKE 'CHARITY%'
            and es.codice_convenzione IS NULL
        ORDER BY es.psp_rag_soc"""

    logger.info(f"[get_wisp_bundles] executing query [{db_query}]")
    cursor = connection.cursor()
    cursor.execute(db_query)
    dataset = cursor.fetchall()
    count = 0
    logger.info(f"[get_wisp_bundles] creating wisp bundles")
    for data in dataset:

        if data[3] == "Paga con Postepay":
            print("trovato")

        if str(data[0]) in psp_blacklist:
            continue

        if count % 100 == 0:
            logger.info(f"[get_wisp_bundles] bundle [{str(count)}]")

        # descrizione_canale_mod_pag management
        canale_mod_pag_code = data[4]
        descrizione_canale_mod_pag = ""
        if canale_mod_pag_code == 1:
            descrizione_canale_mod_pag = "Modello di pagamento immediato multibeneficiario"
        elif canale_mod_pag_code == 2:
            descrizione_canale_mod_pag = "Modello di pagamento differito"
        elif canale_mod_pag_code == 0:
            descrizione_canale_mod_pag = "Modello di pagamento immediato (con redirezione)"
        elif canale_mod_pag_code == 4:
            descrizione_canale_mod_pag = "Modello di pagamento attivato presso il psp"

        # canale_mod_pag management
        canale_mod_pag = ""
        if canale_mod_pag_code == 1:
            canale_mod_pag = "pagopa"
        elif canale_mod_pag_code == 2:
            canale_mod_pag = "pagopa"
        elif canale_mod_pag_code == 0:
            canale_mod_pag = "pagopa"
        elif canale_mod_pag_code == 4:
            canale_mod_pag = "psp"

        # url_informazioni_psp management
        url_informazioni_psp = ""
        if data[0] in cdi_info:
            url_informazioni_psp = cdi_info[data[0]]

        # onus management
        channel: str = data[11]
        on_us: bool = channel.endswith("_ONUS")

        # carte and conto management
        payment_type: str = data[10]
        canale_app: str = data[12]
        carrello_carte: str = data[13]
        carte: bool = payment_type == "CP" and carrello_carte == "Y" and canale_app == "N"
        conto: bool = payment_type in ['BBT', 'BP', 'MYBK', 'AD'] and canale_app == 'N'
        conto_app: bool = payment_type in ["MYBK"]

        # altri_io and altri_wisp management
        altri_io: bool = (canale_app == "Y" and payment_type == "PPAL") or (payment_type == "BPAY")
        altri_wisp: bool = payment_type != "PPAL" and canale_app == 'Y'

        # ABI code management
        abi = data[2]
        id_psp = data[0]
        if abi is None or abi == "" or str(abi).lower() == "tbd":
            if id_psp in psp_code:
                abi = psp_code[id_psp]
                logger.info(f"[get_wisp_bundles] fixed abi for psp [{id_psp}]")

        bundle = Bundle(data[0],                    # idPsp
                        data[1],                    # psp_rag_soc
                        abi,                        # codice_abi
                        data[3],                    # nome_servizio
                        descrizione_canale_mod_pag, # descrizione_canale_mod_pag
                        data[5],                    # inf_desc_serv
                        data[6],                    # inf_url_canale
                        url_informazioni_psp,       # url_informazioni_psp
                        data[7],                    # importo_minimo
                        data[8],                    # importo_massimo
                        data[9],                    # costo_fisso
                        canale_mod_pag_code,        # canale_mod_pag_code
                        payment_type,               # tipo_vers_cod
                        canale_mod_pag,             # canale_mod_pag
                        on_us,                      # on_us
                        carte,                      # carte
                        conto,                      # conto
                        altri_wisp,                 # altri_wisp
                        altri_io,                   # altri_io
                        False,          # is_duplicated
                        conto_app)
        bundles.append(bundle)
        count += 1
    cursor.close()
    logger.info(f"[get_wisp_bundles] wisp bundles created")
    return bundles


def get_gec_bundles():
    # getting cosmos db configuration
    ENDPOINT = os.environ["COSMOS_ENDPOINT"]
    KEY = os.environ["COSMOS_KEY"]

    # getting psp blacklist
    psp_blacklist = os.environ["PSP_BLACKLIST"]
    psp_blacklist = psp_blacklist.split(",")

    # getting configured payment types
    psp_payment_types = os.getenv("PAYMENT_TYPES")
    p_type = json.loads(psp_payment_types)

    print("[get_gec_bundles] Creating cosmos db client")
    client = cosmos_client.CosmosClient(ENDPOINT, {'masterKey': KEY})
    database = client.get_database_client("db")
    container = database.get_container_client("validbundles")

    sql = str("select * from c")
    logger.info(f"[get_gec_bundles] Executing query [{sql}]")

    # Enumerate the returned items
    logger.info("[get_gec_bundles] creating bundles")
    count = 0
    bundles = []
    for item in container.query_items(
            query=sql,
            enable_cross_partition_query=True):

        if str(item['idPsp']) in psp_blacklist:
            continue

        if count % 100 == 0:
            logger.info(f"[get_gec_bundles] bundle [{str(count)}]")

        # onus management
        channel: str = str(item['idChannel'])
        on_us: bool = channel.endswith("_ONUS")

        # carte and conto management
        payment_type: str = str(item['paymentType'])
        cart: bool = True # after CHECKOUT_CART management consolidation -> bool(item['cart'])
        carte: bool = payment_type == "CP" and cart
        conto: bool = payment_type in ["BBT", "BP", "MYBK", "AD", "RPIC", "RICO", "RBPS", "RBPR", "RBPP", "RBPB"]
        conto_app: bool = payment_type in ["MYBK"]

        # altri_io and altri_wisp management
        #- AppIO - Carte PPAL MYBK BancomatPay
        altri_io: bool = payment_type in ["PPAL", "BPAY"]
        altri_wisp: bool = payment_type != "PPAL" and payment_type != "CP" and not conto


        # nome_servizio management
        nome_servizio: str = str(item['name'])
        if str(item['paymentType']) in p_type:
            nome_servizio = p_type[str(item['paymentType'])]
        else:
            logger.info(f"[get_gec_bundles] no configured payment type found for [{str(item['paymentType'])}]")

        bundle = Bundle(str(item['idPsp']),                                 # psp_id
                        str(item['pspBusinessName']),                       # psp_rag_soc
                        str(item['abi']),                                   # codice_abi
                        nome_servizio,                                      # nome_servizio
                        str(item['description']),                           # descrizione_canale_mod_pag
                        str(item['description']),                           # inf_desc_servizio
                        str(item['urlPolicyPsp']),                          # inf_url_canale
                        str(item['urlPolicyPsp']),                          # url_informazioni_psp
                        round(float(item['minPaymentAmount']) / 100, 2),    # importo_minimo
                        round(float(item['maxPaymentAmount']) / 100, 2),    # importp_massimo
                        round(float(item['paymentAmount']) / 100, 2),       # costo_fisso
                        "N/A",                          # canale_mod_pag_code
                        str(item['paymentType']),                           # tipo_vers_code
                        "N/A",                              # canale_mod_pag
                        on_us,
                        carte,
                        conto,
                        altri_wisp,
                        altri_io,
                        False,
                        conto_app)
        count = count + 1
        bundles.append(bundle)

    logger.info("[get_gec_bundles] bundles creation completed")
    return bundles


def build_json_file(bundles: {}):
    logger.info("[build_json_file] preparing file content")
    values = list(bundles.values())
    file_content = {
        "last_Run": "20240730",
        "notebookVersion": "0.4.0",
        "content": values
    }
    json_file_content = json.dumps(file_content)
    logger.info("[build_json_file] file content created")
    logger.info("[build_json_file] writing file...")
    dirname = os.path.dirname(__file__)
    file_name = os.getenv("REPORT_FILE_NAME")
    file_path = dirname + f"/reports/{file_name}"
    logger.info(f"[build_json_file] file path [{file_path}]")
    json_file = open(file_path, "w")
    json_file.write(json_file_content)
    json_file.flush()
    json_file.close()
    logger.info("[build_json_file] file created")


def merge_bundles(old_bundles, new_bundles):
    distinct_bundles = {}

    # dict used to not duplicate bundles from old and new management in case of not matching amount range
    psp_dict = ["SATYLUL1_BBT",
                "PAYTITM1_PPAL",
                "BCITITMM_JIF",
                "PPAYITR1XXX_BBT"] # the list contains blacklisted PSP/payment type tuple

    for item in new_bundles:
        bundle: Bundle = item
        key = (str(bundle.psp_id) + "_" +
               str(int(bundle.importo_minimo)) + "_" +
               str(int(bundle.importo_massimo)) + "_" +
               str(bundle.on_us) + "_" + str(bundle.tipo_vers_cod))

        bundle_key: str = bundle.psp_id + "_" + bundle.tipo_vers_cod
        if bundle_key not in psp_dict:
            psp_dict.append(bundle.psp_id + "_" + bundle.tipo_vers_cod)

        distinct_bundles[key] = bundle.serialize_bundle()

    for item in old_bundles:
        bundle: Bundle = item
        bundle_key: str = bundle.psp_id + "_" + bundle.tipo_vers_cod

        if bundle_key not in psp_dict:
            key = (str(bundle.psp_id) + "_" +
                   str(int(bundle.importo_minimo)) + "_" +
                   str(int(bundle.importo_massimo)) + "_" +
                   str(bundle.on_us) + "_" + str(bundle.tipo_vers_cod))

            distinct_bundles[key] = bundle.serialize_bundle()
        else:
            logger.info(f"[merge_bundles] found old bundle for psp onboarded on GEC, PSPId [{bundle.psp_id}]")

    return distinct_bundles


def write_file_to_bucket():
    # getting configuration parameters
    logging.info("[write_file_to_bucket] getting configuration parameters")
    aws_access_key_id = os.getenv("S3_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("S3_ACCESS_KEY_SECRET")
    bucket_name = os.getenv("S3_BUCKET_NAME")
    report_file_name = os.getenv("REPORT_FILE_NAME")

    # creating aws session
    logging.info("[write_file_to_bucket] creating aws session")
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    # creating s3 resource
    logging.info("[write_file_to_bucket] creating s3 resource")
    s3 = session.resource('s3')

    # creating s3 object
    logging.info(f"[write_file_to_bucket] creating s3 object, bucket name [{bucket_name}], "
                 f"file name [{report_file_name}]")
    object = s3.Object(bucket_name, report_file_name)

    # computing file path
    dirname = os.path.dirname(__file__)
    file_path = dirname + f"/reports/{report_file_name}"
    logging.info(f"[write_file_to_bucket] file path [{file_path}]")

    # uploading file
    logging.info(f"[write_file_to_bucket] uploading file [{file_path}]")
    result = object.put(Body=open(file_path, 'rb'))

    # check result
    logging.info(f"[write_file_to_bucket] check upload result")
    res = result.get('ResponseMetadata')
    response_code = res.get('HTTPStatusCode')
    if response_code == 200:
        logging.info(f"[write_file_to_bucket] file [{file_path}] uploaded successfully")
    else:
        error = result.get("Error")
        error_message = error.get("Message")
        logging.error(f"[write_file_to_bucket] error occurred while uploading file, response code [{response_code}], "
                      f"error message [{error_message}]")


# logging configuration
#file_name = f"{os.getcwd()}/log/reporting.log"
logger = logging.getLogger(__name__)
logging.basicConfig(encoding='utf-8', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# getting pg connection
pg_conn = get_pg_connection()
# getting old bundles
old_b: [] = get_wisp_bundles(pg_conn)
# getting new bundles
new_b: [] = get_gec_bundles()
# merging old and new bundles
merged_b: {} = merge_bundles(old_b, new_b)
# creating file
build_json_file(merged_b)
# write file to s3 bucket
write_file_to_bucket()
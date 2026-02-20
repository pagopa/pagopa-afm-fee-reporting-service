#!/usr/local/bin/python3
import json
import logging
import os
import boto3
import azure.cosmos.cosmos_client as cosmos_client
import psycopg
import decimal
from datetime import datetime


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
                 conto_app,
                 carte_app,
                 touchpoint):

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
        self.carte_app = carte_app
        self.touchpoint = touchpoint


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
            "conto_app": self.conto_app,
            "carte_app": self.carte_app
        }


def get_pg_connection():
    logger.info("[get_pg_connection] getting postgres connection parameters")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("CFG_DB_PASSWORD")
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


def get_gec_bundles():
    # getting cosmos db configuration
    ENDPOINT = os.environ["COSMOS_ENDPOINT"]
    KEY = os.environ["AFM_COSMOS_KEY"]

    # getting psp blacklist
    psp_blacklist = os.environ["PSP_BLACKLIST"]
    psp_blacklist = psp_blacklist.split(",")

    # getting configured payment types
    psp_payment_types = os.getenv("PAYMENT_TYPES")
    p_type = json.loads(psp_payment_types)
    
    # getting configured polycy urls
    psp_policy_url = json.loads(os.getenv("PSP_POLICY_URL"))

    # getting psp with IdPsp to be replaced 
    psp_wrong_id = json.loads(os.getenv("PSP_WRONG_ID"))

    print("[get_gec_bundles] Creating cosmos db client")
    client = cosmos_client.CosmosClient(ENDPOINT, {'masterKey': KEY})
    database = client.get_database_client("db")
    container = database.get_container_client("validbundles")

    sql = str("select * from c where c.type=\"GLOBAL\" and (c.transferCategoryList = null or c.transferCategoryList = [])")
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
        touchpoint: str = str(item['touchpoint'])
        carte: bool = payment_type == "CP" and cart and (touchpoint.lower() == "checkout" or touchpoint.lower() == "any")
        carte_app: bool = payment_type == "CP" and cart and (touchpoint.lower() == "io" or touchpoint.lower() == "any")
        conto: bool = payment_type in ["BBT", "BP", "MYBK", "AD", "RPIC", "RICO", "RBPS", "RBPR", "RBPP", "RBPB"]
        conto_app: bool = payment_type in ["MYBK"]

        # altri_io and altri_wisp management
        #- AppIO - Carte PPAL MYBK BancomatPay
        altri_io: bool = payment_type in ["PPAL", "BPAY", "SATY", "KLRN", "APPL", "RBPP", "GOOG"] and (touchpoint.lower() == "io" or touchpoint.lower() == "any")
        altri_wisp: bool = payment_type != "CP" and not conto and (touchpoint.lower() == "checkout" or touchpoint.lower() == "any")

        # getting configured polycy urls
        purl = str(item['urlPolicyPsp'])
        if item['idPsp'] in psp_policy_url:
            purl = psp_policy_url[item['idPsp']]

        # manage id_psp and abi
        id_psp = str(item['idPsp'])
        abi = str(item['abi'])
        if id_psp in psp_wrong_id:
            id_psp = psp_wrong_id[id_psp]
            abi = id_psp
            
        # nome_servizio management
        nome_servizio: str = str(item['name'])
        if str(item['paymentType']) in p_type:
            nome_servizio = p_type[str(item['paymentType'])]
        else:
            logger.info(f"[get_gec_bundles] no configured payment type found for [{str(item['paymentType'])}]")

        bundle = Bundle(str(id_psp),                                    # psp_id
                        str(item['pspBusinessName']),                   # psp_rag_soc
                        str(abi),                                       # codice_abi
                        nome_servizio,                                  # nome_servizio
                        nome_servizio,                                  # descrizione_canale_mod_pag
                        nome_servizio,                                  # inf_desc_servizio
                        purl,                                           # inf_url_canale
                        purl,                                           # url_informazioni_psp
                        round(float(item['minPaymentAmount']) / 100, 2),# importo_minimo
                        round(float(item['maxPaymentAmount']) / 100, 2),# importp_massimo
                        round(float(item['paymentAmount']) / 100, 2),   # costo_fisso
                        "N/A",                                          # canale_mod_pag_code
                        str(item['paymentType']),                       # tipo_vers_code
                        "N/A",                                          # canale_mod_pag
                        on_us,
                        carte,
                        conto,
                        altri_wisp,
                        altri_io,
                        False,
                        conto_app,
                        carte_app,
                        touchpoint)
        count = count + 1
        bundles.append(bundle.serialize_bundle())

    logger.info("[get_gec_bundles] bundles creation completed")
    return bundles


def build_json_file(bundles: []):
    logger.info("[build_json_file] preparing file content")
    #values = list(bundles.values())
    file_content = {
        "last_Run": datetime.now().strftime("%Y%m%d"),
        "notebookVersion": "0.4.0",
        "content": bundles
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
# getting new bundles
new_b: [] = get_gec_bundles()
# merging old and new bundles
#merged_b: {} = merge_bundles(old_b, new_b)
# creating file
#build_json_file(merged_b)
build_json_file(new_b)
# write file to s3 bucket
write_file_to_bucket()
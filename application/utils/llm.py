import requests
import json
import boto3
import boto3
from botocore.config import Config
from opensearchpy import OpenSearch
from utils import opensearch
from utils.prompt import POSTGRES_DIALECT_PROMPT_CLAUDE3, MYSQL_DIALECT_PROMPT_CLAUDE3, \
    DEFAULT_DIALECT_PROMPT, SEARCH_INTENT_PROMPT_CLAUDE3, CLAUDE3_DATA_ANALYSE_SYSTEM_PROMPT, \
    CLAUDE3_DATA_ANALYSE_USER_PROMPT, AWS_REDSHIFT_DIALECT_PROMPT_CLAUDE3
import os
import logging
from langchain_core.output_parsers import JsonOutputParser
from utils.prompts.generate_prompt import generate_llm_prompt, generate_sagemaker_intent_prompt, \
    generate_sagemaker_sql_prompt, generate_sagemaker_explain_prompt, generate_agent_cot_system_prompt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BEDROCK_AWS_REGION = os.environ.get('BEDROCK_REGION', 'us-west-2')

config = Config(
    region_name=BEDROCK_AWS_REGION,
    signature_version='v4',
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)
# model IDs are here:
# https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-claude.html

bedrock = None
json_parse = JsonOutputParser()
sagemaker_client = None


def get_bedrock_client():
    global bedrock
    if not bedrock:
        bedrock = boto3.client(service_name='bedrock-runtime', config=config)
    return bedrock
def invoke_mode_apihub(model_id,system_prompt,prompt,max_tokens):
    #url = 'https://api-sgp.eclicktech.com.cn/gst/blackholecn/blackhole/overseas/ai/claude3/streamBody'
    url = 'https://api-sgp.eclicktech.com.cn/gst/blackholecn/blackhole/overseas/ai/claude3/claude3Body'

# 定义请求头
    headers = {
        'x-apihub-env': 'prod',
        'x-apihub-ak': '81a9cca49ef3467a8c787c111216ca08',
        'Content-Type': 'application/json'
    }

    # 定义请求数据
    data = {
        "prompt": prompt,
        "modelCode": 1,
        "system": system_prompt
    }
    response = requests.post(url, headers=headers, json=data)
    #print(str(response.status_code), '\n', response.text[:100])
    logger.info("response =  " + response.url)
    fin_response = json.loads(response.text)['data']
    logger.info(f'{fin_response=}')
    return fin_response

# def invoke_mode_apihub(model_id,prompt):
#     url = 'https://api-spp.eclicktech.com.cn/gsi/blackholecn/blackhole/overseaa/ai/clouds/stream'
#     headers = {
#         'x-apihub-env': 'prodhw',
#         'x-apihub-ak': '81a9cca49ef3467a8c787c111216ca88'
#     }
#     params = {
#         'prompt': prompt,
#         'modelCode': model_id
#     }

#     response = requests.get(url, headers=headers, params=params)
#     print(str(response.text.replace('data:','')))
#     #replace('\n','')
#     return response
def invoke_model_claude3(model_id, system_prompt, messages, max_tokens, with_response_stream):
    #user_prompt, system_prompt = generate_prompt(ddl, hints, search_box, examples, model_id, dialect=dialect)

    max_tokens = 2048

    # Prompt with user turn only.
    #user_message = {"role": "user", "content": user_prompt}
    # messages = [user_message]
    # logger.info(f'{system_prompt=}')
    # logger.info(f'{user_message=}')
    # prompt = f"{x} {user_message}"
    response = invoke_mode_apihub(model_id,system_prompt,messages, max_tokens)
    final_response = response

    return final_response

# def invoke_model_claude3(model_id, system_prompt, messages, max_tokens, with_response_stream=False):
#     body = json.dumps(
#         {
#             "anthropic_version": "bedrock-2023-05-31",
#             "max_tokens": max_tokens,
#             "system": system_prompt,
#             "messages": messages,
#             "temperature": 0.01
#         }
#     )

#     if with_response_stream:
#         response = get_bedrock_client().invoke_model_with_response_stream(body=body, modelId=model_id)
#         return response
#     else:
#         response = get_bedrock_client().invoke_model(body=body, modelId=model_id)
#         response_body = json.loads(response.get('body').read())
#         return response_body


def invoke_llama_70b(model_id, system_prompt, user_prompt, max_tokens, with_response_stream=False):
    """
    Invoke LLama-70B model
    :param model_id:
    :param system_prompt:
    :param messages:
    :param max_tokens:
    :param with_response_stream:
    :return:
    """
    try:
        llama3_prompt = """
        <|begin_of_text|><|start_header_id|>system<|end_header_id|>

        {system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

        {user_prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
        """
        body = {
            "prompt": llama3_prompt.format(system_prompt=system_prompt, user_prompt=user_prompt),
            "max_gen_len": 2048,
            "temperature": 0.01,
            "top_p": 0.9
        }
        if with_response_stream:
            response = get_bedrock_client().invoke_model_with_response_stream(body=json.dumps(body), modelId=model_id)
            return response
        else:
            response = get_bedrock_client().invoke_model(
                modelId=model_id, body=json.dumps(body)
            )
            response_body = json.loads(response["body"].read())
            return response_body
    except Exception as e:
        logger.error("Couldn't invoke LLama 70B")
        logger.error(e)



def invoke_mixtral_8x7b(model_id, system_prompt, messages, max_tokens, with_response_stream=False):
    """
    Invokes the Mixtral 8c7B model to run an inference using the input
    provided in the request body.

    :param prompt: The prompt that you want Mixtral to complete.
    :return: List of inference responses from the model.
    """

    try:
        instruction = f"<s>[INST] {system_prompt} \n The question you need to answer is: <question> {messages[0]['content']} </question>[/INST]"
        body = {
            "prompt": instruction,
            # "system": system_prompt,
            # "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.01,
        }

        if with_response_stream:
            response = get_bedrock_client().invoke_model_with_response_stream(body=json.dumps(body), modelId=model_id)
            return response
        else:
            response = get_bedrock_client().invoke_model(
                modelId=model_id, body=json.dumps(body)
            )
            response_body = json.loads(response["body"].read())
            response_body['content'] = response_body['outputs']
            return response_body
    except Exception as e:
        logger.error("Couldn't invoke Mixtral 8x7B")
        logger.error(e)
        raise


def get_sagemaker_client():
    global sagemaker_client
    if not sagemaker_client:
        sagemaker_client = boto3.client(service_name='sagemaker-runtime')
    return sagemaker_client


def invoke_model_sagemaker_endpoint(endpoint_name, body, with_response_stream=False):
    if with_response_stream:
        response = get_sagemaker_client().invoke_endpoint_with_response_stream(
            EndpointName=endpoint_name,
            Body=body,
            ContentType="application/json",
        )
        return response
    else:
        response = get_sagemaker_client().invoke_endpoint(
            EndpointName=endpoint_name,
            Body=body,
            ContentType="application/json",
        )
        response_body = json.loads(response.get('Body').read())
        return response_body


def claude_select_table():
    pass


def generate_prompt(ddl, hints, search_box, sql_examples=None, ner_example=None, model_id=None, dialect='mysql'):
    long_string = ""
    logger.info("generate_prompt ddl is :" + str(ddl))
    for table_name, table_data in ddl.items():
        ddl_string = table_data["col_a"] if 'col_a' in table_data else table_data["ddl"]
        long_string += "-- {}表：{}\n".format(table_name, table_data["tbl_a"] if 'tbl_a' in table_data else table_data[
            "description"])
        long_string += ddl_string
        long_string += "\n"

    ddl = long_string

    logger.info(f'{dialect=}')
    if dialect == 'postgresql':
        dialect_prompt = POSTGRES_DIALECT_PROMPT_CLAUDE3
    elif dialect == 'mysql':
        dialect_prompt = MYSQL_DIALECT_PROMPT_CLAUDE3
    elif dialect == 'redshift':
        dialect_prompt = AWS_REDSHIFT_DIALECT_PROMPT_CLAUDE3
    else:
        dialect_prompt = DEFAULT_DIALECT_PROMPT

    example_sql_prompt = ""
    example_ner_prompt = ""
    if sql_examples:
        for item in sql_examples:
            example_sql_prompt += "Q: " + item['_source']['text'] + "\n"
            example_sql_prompt += "A: ```sql\n" + item['_source']['sql'] + "```\n"

    if ner_example:
        for item in sql_examples:
            example_ner_prompt += "ner: " + item['_source']['entity'] + "\n"
            example_ner_prompt += "ner info:" + item['_source']['comment'] + "\n"

    if example_sql_prompt == "" and example_ner_prompt == "":
        claude_prompt = '''Here is DDL of the database you are working on: 
        ```
        {ddl} 
        ```
        Here are some hints: {hints}
        You need to answer the question: "{question}" in SQL. 
        '''.format(ddl=ddl, hints=hints, question=search_box)
    elif example_sql_prompt != "" and example_ner_prompt == "":
        claude_prompt = '''Here is DDL of the database you are working on:
        ```
        {ddl}
        ```
        Here are some hints: {hints}
        Also, here are some examples of generating SQL using natural language: 
        {examples}
        Now, you need to answer the question: "{question}" in SQL. 
        '''.format(ddl=ddl, hints=hints, examples=example_sql_prompt, question=search_box)
    elif example_sql_prompt == "" and example_ner_prompt != "":
        claude_prompt = '''Here is DDL of the database you are working on:
        ```
        {ddl}
        ```
        Here are some hints: {hints}
        Also, here are some ner info: 
        {examples}
        Now, you need to answer the question: "{question}" in SQL. 
        '''.format(ddl=ddl, hints=hints, examples=example_ner_prompt, question=search_box)
    else:
        claude_prompt = '''Here is DDL of the database you are working on:
        ```
        {ddl}
        ```
        Here are some hints: {hints}
        Here here are some ner info: {examples_ner}
        Also, here are some examples of generating SQL using natural language: 
        {examples_sql}
        Now, you need to answer the question: "{question}" in SQL. 
        '''.format(ddl=ddl, hints=hints, examples_sql=example_sql_prompt, examples_ner=example_ner_prompt,
                   question=search_box)
    print('claude_prompt')

    return claude_prompt, dialect_prompt


def invoke_llm_model(model_id, system_prompt, user_prompt, max_tokens=2018, with_response_stream=False):
    # Prompt with user turn only.
    user_message = {"role": "user", "content": user_prompt}
    messages = [user_message]
    logger.info(f'{system_prompt=}')
    logger.info(f'{messages=}')
    logger.info(f'{model_id=}')
    response = ""
    try:
        if model_id.startswith('anthropic.claude-3-'):
            response = invoke_model_claude3(model_id, system_prompt, str(messages), max_tokens, with_response_stream)
            logger.info(f'{response=}')
        elif model_id.startswith('mistral.mixtral-8x7b'):
            response = invoke_mixtral_8x7b(model_id, system_prompt, messages, max_tokens, with_response_stream)
        elif model_id.startswith('meta.llama3-70b'):
            response = invoke_llama_70b(model_id, system_prompt, user_prompt, max_tokens, with_response_stream)
        if with_response_stream:
            return response
        else:
            if model_id.startswith('meta.llama3-70b'):
                return response["generation"]
            else:
                final_response = response
                #.get("content")[0].get("text")
                return final_response
    except Exception as e:
        logger.error("invoke_llm_model error {}".format(e))
    return response


def text_to_sql(ddl, hints, search_box, sql_examples=None, ner_example=None, model_id=None, dialect='mysql',
                model_provider=None, with_response_stream=False):
    print(ddl)
    user_prompt, system_prompt = generate_llm_prompt(ddl, hints, search_box, sql_examples, ner_example, model_id,
                                                     dialect=dialect)
    max_tokens = 2048
    response = invoke_llm_model(model_id, system_prompt, user_prompt, max_tokens, with_response_stream)
    return response


def sagemaker_to_explain(endpoint_name: str, sql: str, with_response_stream=False):
    body = json.dumps({"query": generate_sagemaker_explain_prompt(sql),
                       "stream": with_response_stream, })
    response = invoke_model_sagemaker_endpoint(endpoint_name, body, with_response_stream)
    logger.info(response)
    if with_response_stream:
        return response
    else:
        # TODO may need to modify response
        return response


def sagemaker_to_sql(ddl, hints, search_box, endpoint_name, sql_examples=None, ner_example=None, dialect='mysql',
                     model_provider=None, with_response_stream=False):
    body = json.dumps({"prompt": generate_sagemaker_sql_prompt(ddl, hints, search_box, sql_examples, ner_example,
                                                               dialect=dialect),
                       "stream": with_response_stream, })
    response = invoke_model_sagemaker_endpoint(endpoint_name, body, with_response_stream)
    logger.info(response)
    if with_response_stream:
        return response
    else:
        # TODO Must modify response
        final_response = '''<query>SELECT i.`item_id`, i.`product_description`, COUNT(it.`event_type`) AS total_purchases
FROM `items` i
JOIN `interactions` it ON i.`item_id` = it.`item_id`
WHERE it.`event_type` = 'purchase'
GROUP BY i.`item_id`, i.`product_description`
ORDER BY total_purchases DESC
LIMIT 10;</query>'''
        return final_response


def get_agent_cot_task(model_id, search_box, ddl, agent_cot_example=None):
    default_agent_cot_task = {"task_1": search_box}
    agent_system_prompt = generate_agent_cot_system_prompt(ddl, agent_cot_example)
    try:
        intent_endpoint = os.getenv("SAGEMAKER_ENDPOINT_INTENT")
        if intent_endpoint:
            # TODO may need to modify the prompt
            body = json.dumps(
                {"query": generate_sagemaker_intent_prompt(search_box, meta_instruction=SEARCH_INTENT_PROMPT_CLAUDE3)})
            response = invoke_model_sagemaker_endpoint(intent_endpoint, body)
            logger.info(f'{response=}')
            intent_result_dict = json_parse.parse(response)
            return intent_result_dict
        else:
            system_prompt = agent_system_prompt
            max_tokens = 2048
            user_message = {"role": "user", "content": search_box}
            messages = [user_message]
            response = invoke_model_claude3(model_id, system_prompt, messages, max_tokens)
            final_response = response.get("content")[0].get("text")
            logger.info(f'{final_response=}')
            intent_result_dict = json_parse.parse(final_response)
            return intent_result_dict
    except Exception as e:
        logger.error("get_agent_cot_task is error:{}".format(e))
        return default_agent_cot_task


def agent_data_analyse(model_id, search_box, sql_data):
    try:
        system_prompt = CLAUDE3_DATA_ANALYSE_SYSTEM_PROMPT
        max_tokens = 2048
        user_prompt = CLAUDE3_DATA_ANALYSE_USER_PROMPT.format(question=search_box, data=sql_data)
        user_message = {"role": "user", "content": user_prompt}
        messages = [user_message]
        response = invoke_model_claude3(model_id, system_prompt, messages, max_tokens)
        final_response = response.get("content")[0].get("text")
        logger.info(f'{final_response=}')
        return final_response
    except Exception as e:
        logger.error("agent_data_analyse is error")
    return ""


# def get_query_intent(model_id, search_box):
#     default_intent = {"intent": "normal_search"}
#     try:
#         intent_endpoint = os.getenv("SAGEMAKER_ENDPOINT_INTENT")
#         if intent_endpoint:
#             # TODO may need to modify the prompt
#             body = json.dumps(
#                 {"query": generate_sagemaker_intent_prompt(search_box, meta_instruction=SEARCH_INTENT_PROMPT_CLAUDE3)})
#             response = invoke_model_sagemaker_endpoint(intent_endpoint, body)
#             logger.info(f'{response=}')
#             intent_result_dict = json_parse.parse(response)
#             return intent_result_dict
#         else:
#             system_prompt = SEARCH_INTENT_PROMPT_CLAUDE3
#             max_tokens = 2048
#             user_message = {"role": "user", "content": search_box}
#             messages = [user_message]
#             response = invoke_model_claude3(model_id, system_prompt, messages, max_tokens)
#             final_response = response.get("content")[0].get("text")
#             logger.info(f'{final_response=}')
#             intent_result_dict = json_parse.parse(final_response)
#             return intent_result_dict
#     except Exception as e:
#         logger.error("get_query_intent is error:{}".format(e))
#         return default_intent

def get_query_intent(model_id, search_box):
    default_intent = {"intent": "normal_search"}
    try:
        system_prompt = SEARCH_INTENT_PROMPT_CLAUDE3
        max_tokens = 2048
        user_message = {"role": "user", "content": search_box}
        # messages = [user_message]
        prompt = f"{system_prompt} {user_message}"
        response = invoke_mode_apihub(model_id,prompt, max_tokens)
        final_response = response.text
        logger.info(f'{final_response=}')
        intent_result_dict = json_parse.parse(final_response)
        return intent_result_dict
    except Exception as e:
        return default_intent


def create_vector_embedding_with_bedrock(text, index_name):
    payload = {"inputText": f"{text}"}
    body = json.dumps(payload)
    modelId = "amazon.titan-embed-text-v1"
    accept = "application/json"
    contentType = "application/json"

    response = get_bedrock_client().invoke_model(
        body=body, modelId=modelId, accept=accept, contentType=contentType
    )
    response_body = json.loads(response.get("body").read())

    embedding = response_body.get("embedding")
    return {"_index": index_name, "text": text, "vector_field": embedding}


def create_vector_embedding_with_sagemaker(endpoint_name, text, index_name):
    model_kwargs = {}
    model_kwargs["batch_size"] = 12
    model_kwargs["max_length"] = 512
    model_kwargs["return_type"] = "dense"
    body = json.dumps({"inputs": [text], **model_kwargs})
    response = invoke_model_sagemaker_endpoint(endpoint_name, body)
    embeddings = response["sentence_embeddings"]
    return {"_index": index_name, "text": text, "vector_field": embeddings["dense_vecs"][0]}


def retrieve_results_from_opensearch(index_name, region_name, domain, opensearch_user, opensearch_password,
                                     query_embedding, top_k=3, host='', port=443, profile_name=None):
    auth = (opensearch_user, opensearch_password)
    if len(host) == 0:
        host = opensearch.get_opensearch_endpoint(domain, region_name)
        port = 443

    # Create the client with SSL/TLS enabled, but hostname verification disabled.
    opensearch_client = OpenSearch(
        hosts=[{'host': host, 'port': port}],
        http_compress=True,  # enables gzip compression for request bodies
        http_auth=auth,
        use_ssl=True,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False
    )
    search_query = {
        "size": top_k,  # Adjust the size as needed to retrieve more or fewer results
        "query": {
            "bool": {
                "filter": {
                    "match_phrase": {
                        "profile": profile_name
                    }
                },
                "must": [
                    {
                        "knn": {
                            "vector_field": {  # Make sure 'vector_field' is the name of your vector field in OpenSearch
                                "vector": query_embedding,
                                "k": top_k  # Adjust k as needed to retrieve more or fewer nearest neighbors
                            }
                        }
                    }
                ]
            }

        }
    }

    # Execute the search query
    response = opensearch_client.search(
        body=search_query,
        index=index_name
    )

    return response['hits']['hits']


def upload_results_to_opensearch(region_name, domain, opensearch_user, opensearch_password, index_name, query, sql,
                                 host='', port=443):
    auth = (opensearch_user, opensearch_password)
    if len(host) == 0:
        host = opensearch.get_opensearch_endpoint(domain, region_name)
        port = 443
    # Create the client with SSL/TLS enabled, but hostname verification disabled.
    opensearch_client = OpenSearch(
        hosts=[{'host': host, 'port': port}],
        http_compress=True,  # enables gzip compression for request bodies
        http_auth=auth,
        use_ssl=True,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False
    )

    # Vector embedding using Amazon Bedrock Titan text embedding
    logger.info(f"Creating embeddings for records")
    record_with_embedding = create_vector_embedding_with_bedrock(query, index_name)

    record_with_embedding['sql'] = sql
    success, failed = opensearch.put_bulk_in_opensearch([record_with_embedding], opensearch_client)
    if success == 1:
        logger.info("Finished creating records using Amazon Bedrock Titan text embedding")
        return True
    else:
        logger.error("Failed to create records using Amazon Bedrock Titan text embedding")
        return False


def generate_suggested_question(search_box, system_prompt, model_id=None):
    max_tokens = 2048
    user_prompt = """
    Here is the input query: {question}. 
    Please generate queries based on the input query.
    """.format(question=search_box)
    user_message = {"role": "user", "content": user_prompt}
    messages = [user_message]
    logger.info(f'{system_prompt=}')
    logger.info(f'{messages=}')
    response = invoke_model_claude3(model_id, system_prompt, messages, max_tokens)
    final_response = response.get("content")[0].get("text")

    return final_response

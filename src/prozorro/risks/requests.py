from prozorro.risks.exceptions import RequestRetryException
from prozorro.risks.settings import BASE_URL
from prozorro_crawler.settings import (
    logger,
    CONNECTION_ERROR_INTERVAL,
    TOO_MANY_REQUESTS_INTERVAL,
)
from json.decoder import JSONDecodeError
import asyncio
import aiohttp


async def get_object_data(session, obj_id, resource="tenders", retries=20):
    retried = 0
    while True:
        try:
            result = await request_object(session=session, obj_id=obj_id, resource=resource, method_name="get")
        except RequestRetryException as e:
            if retried > retries:
                logger.critical(
                    f"Too many retries ({retried}) while requesting object",
                    extra={"MESSAGE_ID": "TOO_MANY_REQUEST_RETRIES"},
                )
            retried += 1
            await asyncio.sleep(e.timeout)
        else:
            return result


async def request_object(session, obj_id, resource, method_name="get"):
    context = {"METHOD": method_name, "OBJ_ID": obj_id, "RESOURCE": resource}
    method = getattr(session, method_name)
    kwargs = {}
    try:
        resp = await method(f"{BASE_URL}/{resource}/{obj_id}", **kwargs)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.warning(
            f"Error for {obj_id} {type(e)}: {e}",
            extra={"MESSAGE_ID": "HTTP_EXCEPTION", **context},
        )
        resp = None
    else:
        if resp.status in (200, 201):
            try:
                response = await resp.json()
            except (aiohttp.ClientPayloadError, JSONDecodeError, asyncio.TimeoutError) as e:
                logger.warning(e, extra={"MESSAGE_ID": "HTTP_EXCEPTION", **context})
            else:
                # ERROR:root:Error while closing connector:
                #    SSLError(1, '[SSL: KRB5_S_INIT] application data after close notify (_ssl.c:2676)')
                # return response["data"] | TypeError: 'NoneType' object is not subscriptable
                if not isinstance(response, dict) or "data" not in response:
                    logger.warning(
                        "Unexpected response contents",
                        extra={
                            "MESSAGE_ID": "REQUEST_UNEXPECTED_ERROR",
                            "CONTENTS": response,
                            **context,
                        },
                    )
                else:
                    return response["data"]
        elif resp.status == 412:
            logger.warning(
                "Precondition Failed while requesting object",
                extra={"MESSAGE_ID": "PRECONDITION_FAILED", **context},
            )
            raise RequestRetryException()
        elif resp.status == 429:
            logger.warning(
                "Too many requests while requesting object",
                extra={"MESSAGE_ID": "TOO_MANY_REQUESTS", **context},
            )
            raise RequestRetryException(timeout=TOO_MANY_REQUESTS_INTERVAL)
        elif resp.status == 409:
            logger.warning(
                f"Resource error while requesting object {obj_id}",
                extra={"MESSAGE_ID": "RESOURCE_ERROR", **context},
            )
        elif resp.status == 403:
            logger.warning(
                f"Forbidden request of object {obj_id}",
                extra={"MESSAGE_ID": "RESOURCE_FORBIDDEN", **context},
            )
        else:
            resp_text = await resp.text()
            logger.error(
                f"Error on requesting object {method_name} {resource} {obj_id}: {resp.status} {resp_text}",
                extra={"MESSAGE_ID": "REQUEST_UNEXPECTED_ERROR", **context},
            )

    raise RequestRetryException(timeout=CONNECTION_ERROR_INTERVAL, response=resp)

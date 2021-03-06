#
#    ICRAR - International Centre for Radio Astronomy Research
#    (c) UWA - The University of Western Australia, 2018
#    Copyright by UWA (in the framework of the ICRAR)
#    All rights reserved
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston,
#    MA 02111-1307  USA

from contextlib import suppress
from aiohttp_security import authorized_userid, permits

from pyvospace.core.exception import VOSpaceError, PermissionDenied, InvalidURI, \
    InvalidJobStateError, InvalidArgument
from pyvospace.core.model import UWSPhase, UWSPhaseLookup, Node, DataNode, ContainerNode, \
    Transfer, Protocol, View, PullFromSpace

from .transfer import perform_transfer_job
from .database import NodeDatabase


async def get_properties_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    properties = request.app['abstract_space'].get_properties()
    if not properties:
        raise InvalidArgument('properties empty')
    results = await request.app['db'].get_contains_properties()
    properties.contains = NodeDatabase._resultset_to_properties(results)
    return properties


async def get_node_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    path = request.path.replace('/vospace/nodes', '')
    node_path = Node(path)
    detail = request.query.get('detail', 'max')
    if detail:
        if detail not in ['min', 'max', 'properties']:
            raise InvalidURI(f'detail invalid: {detail}')
    limit = request.query.get('limit', None)
    if limit:
        try:
            limit = int(limit)
            if limit <= 0:
                raise Exception()
        except:
            raise InvalidURI(f'limit invalid: {limit}')

    async with request.app['db_pool'].acquire() as conn:
        async with conn.transaction():
            node = await request.app['db'].directory(node_path.path, conn, identity)

    if detail == 'min':
        node.remove_properties()

    if isinstance(node, DataNode):
        if detail == 'max':
            node.accepts = request.app['abstract_space'].get_accept_views(node)
            node.provides = request.app['abstract_space'].get_provide_views(node)
    if isinstance(node, ContainerNode):
        if limit:
            node.nodes = node.nodes[:limit]
    return node


async def delete_node_request(app, request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    path = request.path.replace('/vospace/nodes', '')
    async with app['db_pool'].acquire() as conn:
        async with conn.transaction():
            node = await request.app['db'].delete(path, conn, identity)
    with suppress(OSError):
        await app['abstract_space'].delete_storage_node(node)


async def create_node_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    xml_request = await request.text()
    url_path = request.path.replace('/vospace/nodes', '')
    node = Node.fromstring(xml_request)
    if node.path != Node.uri_to_path(url_path):
        raise InvalidURI("Paths do not match")

    async with request.app['db_pool'].acquire() as conn:
        async with conn.transaction():
            await request.app['db'].create(node, conn, identity)
            await request.app['abstract_space'].create_storage_node(node)
            node.accepts = request.app['abstract_space'].get_accept_views(node)
    return node


async def set_node_properties_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    xml_request = await request.text()
    path = request.path.replace('/vospace/nodes', '')
    node = Node.fromstring(xml_request)
    if node.path != Node.uri_to_path(path):
        raise InvalidURI("Paths do not match")

    async with request.app['db_pool'].acquire() as conn:
        async with conn.transaction():
            node = await request.app['db'].update(node, conn, identity)
    return node


async def create_transfer_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    job_xml = await request.text()
    transfer = Transfer.fromstring(job_xml)
    if not await request.app.permits(identity, 'createTransfer', context=transfer):
        raise PermissionDenied('creating transfer job denied.')
    job = await request.app['executor'].create(transfer, identity, UWSPhase.Pending)
    return job


async def sync_transfer_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    redirect_endpoint = False
    if request.query:
        target = request.query.get('TARGET')
        direction = request.query.get('DIRECTION')
        protocol_uri = request.query.get('PROTOCOL')
        view_uri = request.query.get('VIEW')
        security_uri = request.query.get('SECURITYMETHOD')
        transfer = Transfer.create_transfer(target=target, direction=direction, keep_bytes=False)
        protocol = Protocol.create_protocol(uri=protocol_uri, security_method_uri=security_uri)
        transfer.set_protocols([protocol])
        if view_uri:
            transfer.view = View(view_uri)
        if isinstance(transfer, PullFromSpace):
            redirect_request = request.query.get('REQUEST')
            if redirect_request != 'redirect':
                raise InvalidArgument('REQUEST must be set to request')
            redirect_endpoint = True

    else:
        job_xml = await request.text()
        if not job_xml:
            raise InvalidURI("Empty transfer request.")
        transfer = Transfer.fromstring(job_xml)

    if not await request.app.permits(identity, 'createTransfer', context=transfer):
        raise PermissionDenied('creating transfer job denied.')
    job = await request.app['executor'].create(transfer, identity, UWSPhase.Executing)
    endpoint = await perform_transfer_job(job, request.app, identity, sync=True, redirect=redirect_endpoint)
    return job, endpoint


async def get_job_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    job_id = request.match_info.get('job_id', None)
    job = await request.app['executor'].get(job_id)
    if identity != job.owner:
        raise PermissionDenied(f'{identity} is not the owner of the job.')
    return job


async def get_transfer_details_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    job_id = request.match_info.get('job_id', None)
    job = await request.app['executor'].get_uws_job(job_id)
    if identity != job['owner']:
        raise PermissionDenied(f'{identity} is not the owner of the job.')
    if job['phase'] < UWSPhase.Executing:
        raise InvalidJobStateError('Job not EXECUTING')
    if not job['transfer']:
        raise VOSpaceError(400, 'No transferDetails for this job.')
    return job['transfer']


async def get_job_phase_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    job_id = request.match_info.get('job_id', None)
    job = await request.app['executor'].get_uws_job_phase(job_id)
    if identity != job['owner']:
        raise PermissionDenied(f'{identity} is not the owner of the job.')
    return UWSPhaseLookup[job['phase']]


async def modify_job_request(request):
    identity = await authorized_userid(request)
    if identity is None:
        raise PermissionDenied(f'Credentials not found.')
    job_id = request.match_info.get('job_id', None)
    uws_cmd = await request.text()
    if not uws_cmd:
        raise VOSpaceError(400, "Invalid Request. Empty UWS phase input.")

    phase = uws_cmd.upper()
    if phase == "PHASE=RUN":
        await request.app['executor'].execute(job_id, identity, perform_transfer_job,
                                              request.app, identity, False, False)
    elif phase == "PHASE=ABORT":
        await request.app['executor'].abort(job_id, identity)
    else:
        raise VOSpaceError(400, f"Invalid Request. Unknown UWS phase input {uws_cmd}")

    return job_id

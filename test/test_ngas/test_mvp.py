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

import unittest
import asyncio
import logging
import hashlib
import io

from aiohttp import web

from pyvospace.core.model import *
from pyvospace.server import set_fuzz, set_busy_fuzz
from pyvospace.server.spaces.ngas.storage.ngas_storage import NGASStorageServer
from test_base import TestBase

class TestPushPull(TestBase):

    def setUp(self):

        logger=logging.getLogger("aiohttp.web")
        logger.setLevel(logging.DEBUG)

        super().setUp()
        self.loop.run_until_complete(self._setup())
        ngas_server = self.loop.run_until_complete(NGASStorageServer.create(self.config_filename, logger=logger))

        self.ngas_runner = web.AppRunner(ngas_server)
        self.loop.run_until_complete(self.ngas_runner.setup())
        self.ngas_site = web.TCPSite(self.ngas_runner, 'localhost', 8083)
        self.loop.run_until_complete(self.ngas_site.start())

    async def _setup(self):
        if not os.path.exists('/tmp/download'):
            os.makedirs('/tmp/download')
        await self.create_file('/tmp/datafile.dat')
        await self.create_tar('/tmp/mytar.tar.gz')

    def tearDown(self):
        self.loop.run_until_complete(self.delete('http://localhost:8080/vospace/nodes/root'))
        self.loop.run_until_complete(self.delete('http://localhost:8080/vospace/nodes/datanode'))
        self.loop.run_until_complete(self.delete('http://localhost:8080/vospace/nodes/syncdatanode'))
        self.loop.run_until_complete(self.delete('http://localhost:8080/vospace/nodes/syncdatanode1.fits'))
        self.loop.run_until_complete(self.delete('http://localhost:8080/vospace/nodes/root/mytar.tar.gz'))
        self.loop.run_until_complete(self.ngas_runner.shutdown())
        self.loop.run_until_complete(self.ngas_runner.cleanup())
        super().tearDown()

    def test_push_to_node(self):
        async def run():
            root_node = ContainerNode('/root')
            await self.create_node(root_node)

            node = DataNode('/root/datafile.dat',
                properties=[Property('ivo://ivoa.net/vospace/core#title', "datafile.dat", True),
                            Property('ivo://ivoa.net/vospace/core#contributor', "dave", True)])
            await self.create_node(node)

            # Push to leaf node
            push = PushToSpace(node, [HTTPPut()], params=[Parameter("ivo://ivoa.net/vospace/core#length", 1234)])
            #
            transfer = await self.sync_transfer_node(push)
            put_end = transfer.protocols[0].endpoint.url
            await self.push_to_space(put_end, '/tmp/datafile.dat', expected_status=200)

            # # Pull from leaf node
            # pull = PullFromSpace(node, [HTTPGet()])
            # transfer = await self.sync_transfer_node(pull)
            # pull_end = transfer.protocols[0].endpoint.url
            # print(f"pull_end is {pull_end}")
            # await self.pull_from_space(pull_end, '/tmp/download/')

            # # Make some hashes
            # sha1_orig = hashlib.sha1()
            # # Verify the files are the same
            # async with aiofiles.open("/tmp/mytar.tar.gz", "rb") as fd:
            #     while True:
            #         buffer = fd.read(io.DEFAULT_BUFFER_SIZE)
            #         if not buffer:
            #             break
            #         sha1_orig.update(buffer)
            #
            # sha1_ngas = hashlib.sha1()
            # async with aiofiles.open("/tmp/download/mytar.tar.gz", "rb") as fd:
            #     while True:
            #         buffer = fd.read(io.DEFAULT_BUFFER_SIZE)
            #         if not buffer:
            #             break
            #         sha1_ngas.update(buffer)
            #
            # self.assertEqual(sha1_ngas, sha1_orig, msg="Downloaded file not the same as uploaded file")

        self.loop.run_until_complete(run())

    # def test_pull_from_node(self):
    #     async def run():
    #         root_node = ContainerNode('/root')
    #         await self.create_node(root_node)
    #
    #         node = DataNode('/root/datafile.dat',
    #             properties=[Property('ivo://ivoa.net/vospace/core#title', "datafile.dat", True),
    #                         Property('ivo://ivoa.net/vospace/core#contributor', "dave", True)])
    #         await self.create_node(node)
    #
    #         # Pull from leaf node
    #         pull = PullFromSpace(node, [HTTPGet()])
    #         transfer = await self.sync_transfer_node(pull)
    #         pull_end = transfer.protocols[0].endpoint.url
    #         print(f"pull_end is {pull_end}")
    #         await self.pull_from_space(pull_end, '/tmp/download/')
    #
    #         # # Make some hashes
    #         # sha1_orig = hashlib.sha1()
    #         # # Verify the files are the same
    #         # async with aiofiles.open("/tmp/mytar.tar.gz", "rb") as fd:
    #         #     while True:
    #         #         buffer = fd.read(io.DEFAULT_BUFFER_SIZE)
    #         #         if not buffer:
    #         #             break
    #         #         sha1_orig.update(buffer)
    #         #
    #         # sha1_ngas = hashlib.sha1()
    #         # async with aiofiles.open("/tmp/download/mytar.tar.gz", "rb") as fd:
    #         #     while True:
    #         #         buffer = fd.read(io.DEFAULT_BUFFER_SIZE)
    #         #         if not buffer:
    #         #             break
    #         #         sha1_ngas.update(buffer)
    #         #
    #         # self.assertEqual(sha1_ngas, sha1_orig, msg="Downloaded file not the same as uploaded file")
    #
    #     self.loop.run_until_complete(run())

if __name__ == '__main__':
    unittest.main()
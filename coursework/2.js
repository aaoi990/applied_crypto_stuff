/* eslint-disable no-console */
'use strict'

const Libp2p = require('../../')
const TCP = require('libp2p-tcp')
const Mplex = require('libp2p-mplex')
const { NOISE } = require('libp2p-noise')
const crypto = require('crypto')
const CID = require('cids')
const multihash = require('multihashes')
const KadDHT = require('libp2p-kad-dht')
const Bootstrap = require('libp2p-bootstrap')


const all = require('it-all')
const delay = require('delay')

const bootstrapMultiaddrs = [
  '/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb',
  '/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN'
]


const createNode = async () => {
  const node = await Libp2p.create({
    addresses: {
      listen: ['/ip4/0.0.0.0/tcp/0']
    },
    modules: {
      transport: [TCP],
      streamMuxer: [Mplex],
      connEncryption: [NOISE],
      dht: KadDHT,
    },
    config: {
      dht: {
        enabled: true
      }
    }
  })

  await node.start()
  return node
}

;(async () => {
  const [node1, node2, node3] = await Promise.all([
    createNode(),
    createNode(),
    createNode()
  ])

  node1.peerStore.addressBook.set(node2.peerId, node2.multiaddrs)
  node2.peerStore.addressBook.set(node3.peerId, node3.multiaddrs)

  await Promise.all([
    node1.dial(node2.peerId),
    node2.dial(node3.peerId)
  ])

  // Wait for onConnect handlers in the DHT
  await delay(100)

  const hash = crypto.createHash('sha256').update('hello word!').digest()
  const encoded = multihash.encode(hash, 'sha2-256')
  let cid = new CID(multihash.toB58String(encoded))
  console.log('CID:', cid)

  await node1.contentRouting.provide(cid)
  await node2.contentRouting.provide(cid)

  console.log('Node %s is providing %s', node1.peerId.toB58String(), cid.toBaseEncodedString())

  // wait for propagation
  await delay(300)

  const providers = await all(node3.contentRouting.findProviders(cid, { timeout: 3000 }))

  console.log('Found provider:', providers[0].id.toB58String(), providers)
  node1.stop()
  node2.stop()
  node3.stop()
})();

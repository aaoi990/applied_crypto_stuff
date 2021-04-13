/* eslint-disable no-console */
'use strict'

const Libp2p = require('libp2p')
const TCP = require('libp2p-tcp')
const uint8ArrayFromString = require('uint8arrays/from-string')
const Mplex = require('libp2p-mplex')
const { NOISE } = require('libp2p-noise')
const crypto = require('crypto')
const CID = require('cids')
const multihash = require('multihashes')
const KadDHT = require('libp2p-kad-dht')
const utils = require('libp2p-kad-dht/src/utils')
const delay = require('delay')
const distance = require('xor-distance')

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
      dht: {                        // The DHT options (and defaults) can be found in its documentation
        kBucketSize: 20,
        enabled: true,
        randomWalk: {
          enabled: false,            // Allows to disable discovery (enabled by default)
          interval: 300e3,
          timeout: 10e3
        }
      }
    }
  })
  await node.start()
  return node
}

const create_CID = (content) => {
  const hash = crypto.createHash('sha256').update(content).digest()
  const encoded = multihash.encode(hash, 'sha2-256')
  let cid = new CID(multihash.toB58String(encoded))
  return cid
}

const map_nodes_to_peerids = (nodes) => {
  let node_mappings = []
  let node_peerIds = []
  nodes.forEach((node) => {
    node_mappings.push(node.peerId.toB58String())
    node_peerIds.push(node.peerId)
  })
  return { node_mappings, node_peerIds }
}

const sort_closest_nodes = async (peers, query, node_mappings) => {
  let query_key = uint8ArrayFromString(query)
  let dhtkey = await utils.convertBuffer(query_key)
  let sorted_peers = await utils.sortClosestPeers(node_mappings, dhtkey)
  let closest_peers = []
  for await (let sorted of sorted_peers) {
    let peer = peers.findIndex(element => element.peerId.toB58String() == sorted._idB58String)
     closest_peers.push(peer)
  }
  return closest_peers
}

;(async () => {
  const nodes = await Promise.all([
    createNode(), createNode(), createNode(), createNode(), createNode(), createNode(), createNode(), createNode(), createNode(), createNode()
  ])

  for(let index = 0; index < nodes.length - 1; index++) {
    nodes[index].peerStore.addressBook.set(nodes[index + 1].peerId, nodes[index + 1].multiaddrs)
  }

  await Promise.all([
    nodes[0].dial(nodes[1].peerId),
    nodes[1].dial(nodes[2].peerId)
  ])

  const { node_mappings, node_peerIds } = map_nodes_to_peerids(nodes)
  //console.log(node_mappings, node_peerIds)
  // Wait for onConnect handlers in the DHT
  await delay(10000)


  let cid = create_CID("hello world!")
  await nodes[0].contentRouting.provide(cid)

  console.log('Node %s is providing %s', nodes[0].peerId.toB58String(), cid.toBaseEncodedString())

  // wait for propagation

  const closest = await sort_closest_nodes(nodes, 'hello world!', node_peerIds)
  console.log("Peers that are closest to the target provider: ")
  for(let index = 0; index < closest.length; index++) {
    console.log("Node ", index + " : " + node_mappings[index])
  }



  //const providers = await all(nodes[2].contentRouting.findProviders(cid, { timeout: 3000 }))

  //console.log('Found provider:', providers[0].id.toB58String(), providers)

  // nodes.forEach((node) => {
  //   node.stop()
  // })
})();

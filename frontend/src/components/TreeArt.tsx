/** The tree from the OCBC Tree slide, cropped to the tree itself (the slide's own wording sits to its left). */
export function TreeArt({ caption }: { caption?: string }) {
  return (
    <figure className="tree-art">
      <div className="tree-art-img" role="img" aria-label="A large tree rooted in documents, a shield and a bank, in front of the Singapore skyline." />
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  );
}
